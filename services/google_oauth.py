"""Google OAuth: client HTTP, stato CSRF e sign-in."""

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
    oauth_state_jti,
    oauth_state_subject,
    verify_oauth_state,
)

logger = logging.getLogger(__name__)

GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_USERINFO_URL = "https://www.googleapis.com/oauth2/v3/userinfo"
TOKEN_TYP_GOOGLE_OAUTH_STATE = "google_oauth_state"
TOKEN_TYP_GOOGLE_OAUTH_LINK = "google_oauth_link"
PROVIDER_LABEL = "Google"

GoogleOAuthError = OAuthSignInError
GoogleOAuthNotConfigured = OAuthNotConfiguredError
GoogleOAuthStateError = OAuthStateError
GoogleOAuthExchangeError = OAuthExchangeError
GoogleOAuthProfileError = OAuthProfileError
GoogleOAuthAccountError = OAuthAccountError
GoogleUserProfile = SocialUserProfile
GoogleAuthorizePayload = OAuthAuthorizePayload
GoogleSignInResult = OAuthSignInResult


class GoogleOAuthService:
    """Collo di bottiglia OAuth Google: authorize, callback, persistenza utente."""

    def __init__(self, settings: Settings | None = None) -> None:
        self._settings = settings or get_settings()

    @property
    def is_configured(self) -> bool:
        """True se client id/secret e redirect URI backend sono valorizzati."""
        return bool(
            self._settings.google_oauth_client_id.strip()
            and self._settings.google_oauth_client_secret.strip()
            and self._settings.google_oauth_redirect_uri.strip()
        )

    def _require_configured(self) -> None:
        if not self.is_configured:
            raise GoogleOAuthNotConfigured("Google OAuth is not configured")

    def _http_client(self) -> httpx.Client:
        return httpx.Client(timeout=30.0)

    def create_oauth_state(self) -> str:
        """JWT firmato anti-CSRF (``typ=google_oauth_state``)."""
        self._require_configured()
        return create_oauth_state(
            token_typ=TOKEN_TYP_GOOGLE_OAUTH_STATE,
            expire_minutes=self._settings.google_oauth_state_expire_minutes,
        )

    def verify_oauth_state(self, state: str) -> None:
        """Valida state JWT."""
        self._require_configured()
        verify_oauth_state(token_typ=TOKEN_TYP_GOOGLE_OAUTH_STATE, state=state)

    def build_authorize_payload(self) -> GoogleAuthorizePayload:
        """Genera URL Google e state per avviare il flusso."""
        state = self.create_oauth_state()
        return GoogleAuthorizePayload(
            authorization_url=self._authorization_url(state),
            state=state,
        )

    def build_link_authorize_payload(self, user_id: uuid.UUID) -> GoogleAuthorizePayload:
        """Avvia collegamento Google all'utente già autenticato (Settings)."""
        self._require_configured()
        state = create_oauth_state(
            token_typ=TOKEN_TYP_GOOGLE_OAUTH_LINK,
            expire_minutes=self._settings.google_oauth_state_expire_minutes,
            subject=str(user_id),
        )
        return GoogleAuthorizePayload(
            authorization_url=self._authorization_url(state),
            state=state,
        )

    def _authorization_url(self, state: str) -> str:
        params = {
            "client_id": self._settings.google_oauth_client_id.strip(),
            "redirect_uri": self._settings.google_oauth_redirect_uri.strip(),
            "response_type": "code",
            "scope": "openid email profile",
            "state": state,
            "access_type": "online",
            "prompt": "select_account",
        }
        return f"{GOOGLE_AUTH_URL}?{urlencode(params)}"

    def exchange_code_for_tokens(self, code: str) -> dict[str, Any]:
        """Scambia authorization code con token Google."""
        self._require_configured()
        data = {
            "code": code.strip(),
            "client_id": self._settings.google_oauth_client_id.strip(),
            "client_secret": self._settings.google_oauth_client_secret.strip(),
            "redirect_uri": self._settings.google_oauth_redirect_uri.strip(),
            "grant_type": "authorization_code",
        }
        with self._http_client() as client:
            response = client.post(
                GOOGLE_TOKEN_URL,
                data=data,
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )
        if response.status_code != 200:
            logger.warning("Google token exchange failed: %s", response.text[:500])
            raise GoogleOAuthExchangeError("Failed to exchange authorization code")
        return response.json()

    def fetch_user_profile(self, access_token: str) -> GoogleUserProfile:
        """Recupera profilo da Google userinfo."""
        with self._http_client() as client:
            response = client.get(
                GOOGLE_USERINFO_URL,
                headers={"Authorization": f"Bearer {access_token.strip()}"},
            )
        if response.status_code != 200:
            logger.warning("Google userinfo failed: %s", response.text[:500])
            raise GoogleOAuthExchangeError("Failed to fetch Google user profile")
        return self._parse_user_profile(response.json())

    def fetch_profile_for_code(self, code: str) -> GoogleUserProfile:
        """Code → token Google → userinfo normalizzato."""
        token_payload = self.exchange_code_for_tokens(code)
        access = (token_payload.get("access_token") or "").strip()
        if not access:
            raise GoogleOAuthExchangeError("Google did not return an access token")
        return self.fetch_user_profile(access)

    def sign_in_with_code(self, db: Session, *, code: str, state: str) -> GoogleSignInResult:
        """Flusso completo: valida state, profilo Google, utente DB, token Trustnet."""
        self.verify_oauth_state(state)
        profile = self.fetch_profile_for_code(code)
        return complete_social_sign_in(
            db,
            provider=OAuthProvider.GOOGLE,
            profile=profile,
            provider_label=PROVIDER_LABEL,
        )

    def link_with_code(self, db: Session, *, code: str, state: str) -> None:
        """Collega Google all'utente indicato nello state (senza nuova sessione)."""
        payload = verify_oauth_state(token_typ=TOKEN_TYP_GOOGLE_OAUTH_LINK, state=state)
        user_id = oauth_state_subject(payload)
        profile = self.fetch_profile_for_code(code)
        complete_social_link(
            db,
            user_id=user_id,
            provider=OAuthProvider.GOOGLE,
            profile=profile,
            provider_label=PROVIDER_LABEL,
        )

    def build_frontend_redirect_url(self, result: GoogleSignInResult) -> str:
        """Redirect verso FE con token in query."""
        return build_frontend_redirect_url(
            self._settings.google_oauth_frontend_callback_url,
            result,
        )

    def build_frontend_link_redirect_url(self, *, error: str | None = None) -> str:
        """Redirect verso Settings dopo collegamento (successo o errore)."""
        return build_frontend_connected_accounts_url(
            self._settings.google_oauth_frontend_callback_url,
            provider=OAuthProvider.GOOGLE.value,
            error=error,
        )

    def _parse_user_profile(self, raw: dict[str, Any]) -> GoogleUserProfile:
        sub = (raw.get("sub") or "").strip()
        email = (raw.get("email") or "").strip().lower()
        email_verified = bool(raw.get("email_verified"))
        if not sub or not email:
            raise GoogleOAuthProfileError("Google profile missing sub or email")
        if not email_verified:
            raise GoogleOAuthProfileError("Google email is not verified")
        given = (raw.get("given_name") or "").strip() or "User"
        family = (raw.get("family_name") or "").strip() or "User"
        picture = (raw.get("picture") or "").strip() or None
        return GoogleUserProfile(
            sub=sub,
            email=email,
            email_verified=email_verified,
            given_name=given,
            family_name=family,
            picture=picture,
            raw=raw,
        )


def secrets_hex() -> str:
    """Retrocompat: JTI state OAuth."""
    return oauth_state_jti()


@lru_cache
def get_google_oauth_service() -> GoogleOAuthService:
    """Dependency FastAPI: client Google OAuth singleton."""
    return GoogleOAuthService()
