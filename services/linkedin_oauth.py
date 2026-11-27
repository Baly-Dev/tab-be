"""LinkedIn OAuth (OpenID Connect): client HTTP, state CSRF e sign-in."""

from __future__ import annotations

import logging
import uuid
from functools import lru_cache
from typing import Any
from urllib.parse import urlencode

import httpx
from sqlalchemy.orm import Session

from config import OAuthProvider, Settings, get_settings
from auth.errors.oauth_errors import (
    OAuthAccountError,
    OAuthExchangeError,
    OAuthNotConfiguredError,
    OAuthProfileError,
    OAuthSignInError,
    OAuthStateError,
)
from auth.utils.oauth import (
    OAuthAuthorizePayload,
    OAuthSignInResult,
    SocialUserProfile,
    build_frontend_connected_accounts_url,
    build_frontend_redirect_url,
    complete_social_link,
    complete_social_sign_in,
    create_oauth_state,
    split_full_name,
    verify_oauth_state,
    oauth_state_subject,
)

logger = logging.getLogger(__name__)

LINKEDIN_AUTH_URL = "https://www.linkedin.com/oauth/v2/authorization"
LINKEDIN_TOKEN_URL = "https://www.linkedin.com/oauth/v2/accessToken"
LINKEDIN_USERINFO_URL = "https://api.linkedin.com/v2/userinfo"
TOKEN_TYP_LINKEDIN_OAUTH_STATE = "linkedin_oauth_state"
TOKEN_TYP_LINKEDIN_OAUTH_LINK = "linkedin_oauth_link"
PROVIDER_LABEL = "LinkedIn"

LinkedInOAuthError = OAuthSignInError
LinkedInOAuthNotConfigured = OAuthNotConfiguredError
LinkedInOAuthStateError = OAuthStateError
LinkedInOAuthExchangeError = OAuthExchangeError
LinkedInOAuthProfileError = OAuthProfileError
LinkedInOAuthAccountError = OAuthAccountError
LinkedInUserProfile = SocialUserProfile
LinkedInAuthorizePayload = OAuthAuthorizePayload
LinkedInSignInResult = OAuthSignInResult


class LinkedInOAuthService:
    """Collo di bottiglia OAuth LinkedIn: authorize, callback, persistenza utente."""

    def __init__(self, settings: Settings | None = None) -> None:
        self._settings = settings or get_settings()

    @property
    def is_configured(self) -> bool:
        """True se client id/secret e redirect URI backend sono valorizzati."""
        return bool(
            self._settings.linkedin_oauth_client_id.strip()
            and self._settings.linkedin_oauth_client_secret.strip()
            and self._settings.linkedin_oauth_redirect_uri.strip()
        )

    def _require_configured(self) -> None:
        if not self.is_configured:
            raise LinkedInOAuthNotConfigured("LinkedIn OAuth is not configured")

    def _http_client(self) -> httpx.Client:
        return httpx.Client(timeout=30.0)

    def create_oauth_state(self) -> str:
        """JWT firmato anti-CSRF (``typ=linkedin_oauth_state``)."""
        self._require_configured()
        return create_oauth_state(
            token_typ=TOKEN_TYP_LINKEDIN_OAUTH_STATE,
            expire_minutes=self._settings.linkedin_oauth_state_expire_minutes,
        )

    def verify_oauth_state(self, state: str) -> None:
        """Valida state JWT."""
        self._require_configured()
        verify_oauth_state(token_typ=TOKEN_TYP_LINKEDIN_OAUTH_STATE, state=state)

    def build_authorize_payload(self) -> LinkedInAuthorizePayload:
        """Genera URL LinkedIn e state (Sign In with LinkedIn / OpenID Connect)."""
        state = self.create_oauth_state()
        return LinkedInAuthorizePayload(
            authorization_url=self._authorization_url(state),
            state=state,
        )

    def build_link_authorize_payload(self, user_id: uuid.UUID) -> LinkedInAuthorizePayload:
        """Avvia collegamento LinkedIn all'utente già autenticato (Settings)."""
        self._require_configured()
        state = create_oauth_state(
            token_typ=TOKEN_TYP_LINKEDIN_OAUTH_LINK,
            expire_minutes=self._settings.linkedin_oauth_state_expire_minutes,
            subject=str(user_id),
        )
        return LinkedInAuthorizePayload(
            authorization_url=self._authorization_url(state),
            state=state,
        )

    def _authorization_url(self, state: str) -> str:
        params = {
            "client_id": self._settings.linkedin_oauth_client_id.strip(),
            "redirect_uri": self._settings.linkedin_oauth_redirect_uri.strip(),
            "response_type": "code",
            "scope": "openid profile email",
            "state": state,
        }
        return f"{LINKEDIN_AUTH_URL}?{urlencode(params)}"

    def exchange_code_for_tokens(self, code: str) -> dict[str, Any]:
        """Scambia authorization code con token LinkedIn."""
        self._require_configured()
        data = {
            "code": code.strip(),
            "client_id": self._settings.linkedin_oauth_client_id.strip(),
            "client_secret": self._settings.linkedin_oauth_client_secret.strip(),
            "redirect_uri": self._settings.linkedin_oauth_redirect_uri.strip(),
            "grant_type": "authorization_code",
        }
        with self._http_client() as client:
            response = client.post(
                LINKEDIN_TOKEN_URL,
                data=data,
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )
        if response.status_code != 200:
            logger.warning("LinkedIn token exchange failed: %s", response.text[:500])
            raise LinkedInOAuthExchangeError("Failed to exchange authorization code")
        return response.json()

    def fetch_user_profile(self, access_token: str) -> LinkedInUserProfile:
        """Recupera profilo da LinkedIn userinfo (OpenID Connect)."""
        with self._http_client() as client:
            response = client.get(
                LINKEDIN_USERINFO_URL,
                headers={"Authorization": f"Bearer {access_token.strip()}"},
            )
        if response.status_code != 200:
            logger.warning("LinkedIn userinfo failed: %s", response.text[:500])
            raise LinkedInOAuthExchangeError("Failed to fetch LinkedIn user profile")
        return self._parse_user_profile(response.json())

    def fetch_profile_for_code(self, code: str) -> LinkedInUserProfile:
        """Code → token LinkedIn → userinfo normalizzato."""
        token_payload = self.exchange_code_for_tokens(code)
        access = (token_payload.get("access_token") or "").strip()
        if not access:
            raise LinkedInOAuthExchangeError("LinkedIn did not return an access token")
        return self.fetch_user_profile(access)

    def sign_in_with_code(self, db: Session, *, code: str, state: str) -> LinkedInSignInResult:
        """Flusso completo: valida state, profilo LinkedIn, utente DB, token Trustnet."""
        self.verify_oauth_state(state)
        profile = self.fetch_profile_for_code(code)
        return complete_social_sign_in(
            db,
            provider=OAuthProvider.LINKEDIN,
            profile=profile,
            provider_label=PROVIDER_LABEL,
        )

    def link_with_code(self, db: Session, *, code: str, state: str) -> None:
        """Collega LinkedIn all'utente indicato nello state (senza nuova sessione)."""
        payload = verify_oauth_state(token_typ=TOKEN_TYP_LINKEDIN_OAUTH_LINK, state=state)
        user_id = oauth_state_subject(payload)
        profile = self.fetch_profile_for_code(code)
        complete_social_link(
            db,
            user_id=user_id,
            provider=OAuthProvider.LINKEDIN,
            profile=profile,
            provider_label=PROVIDER_LABEL,
        )

    def build_frontend_redirect_url(self, result: LinkedInSignInResult) -> str:
        """Redirect verso FE con handoff monouso nel fragment."""
        return build_frontend_redirect_url(
            self._settings.linkedin_oauth_frontend_callback_url,
            result,
        )

    def build_frontend_link_redirect_url(self, *, error: str | None = None) -> str:
        """Redirect verso Settings dopo collegamento (successo o errore)."""
        return build_frontend_connected_accounts_url(
            self._settings.linkedin_oauth_frontend_callback_url,
            provider=OAuthProvider.LINKEDIN.value,
            error=error,
        )

    def _parse_user_profile(self, raw: dict[str, Any]) -> LinkedInUserProfile:
        sub = (raw.get("sub") or "").strip()
        email = (raw.get("email") or "").strip().lower()
        email_verified = raw.get("email_verified")
        if email_verified is None and email:
            email_verified = True
        email_verified = bool(email_verified)
        if not sub or not email:
            raise LinkedInOAuthProfileError("LinkedIn profile missing sub or email")
        if not email_verified:
            raise LinkedInOAuthProfileError("LinkedIn email is not verified")
        given = (raw.get("given_name") or "").strip()
        family = (raw.get("family_name") or "").strip()
        if not given or not family:
            given, family = split_full_name((raw.get("name") or "").strip())
        picture = (raw.get("picture") or "").strip() or None
        return LinkedInUserProfile(
            sub=sub,
            email=email,
            email_verified=email_verified,
            given_name=given,
            family_name=family,
            picture=picture,
            raw=raw,
        )


@lru_cache
def get_linkedin_oauth_service() -> LinkedInOAuthService:
    """Dependency FastAPI: client LinkedIn OAuth singleton."""
    return LinkedInOAuthService()
