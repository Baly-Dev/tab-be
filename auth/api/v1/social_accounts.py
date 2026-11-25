"""Collegamento e scollegamento account OAuth (utente autenticato)."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from auth.errors.account_errors import (
    http_error_cannot_unlink_last_login,
    http_error_social_account_not_linked,
    http_error_unlink_social_account_failed,
)
from auth.errors.oauth_errors import OAuthSignInError, http_error_from_oauth
from auth.models.social_account import AuthSocialAccount
from auth.schemas.social_accounts import LinkSocialAuthorizeResponse, UnlinkSocialAccountResponse
from auth.utils.helpers import AuthenticatedUser
from auth.utils.login_methods import count_login_methods
from config import OAuthProvider
from config.db.session import get_db
from services.google_oauth import GoogleOAuthService, get_google_oauth_service
from services.linkedin_oauth import LinkedInOAuthService, get_linkedin_oauth_service

router = APIRouter(prefix="/social-accounts")

_PROVIDER_LABELS = {
    OAuthProvider.GOOGLE: "Google",
    OAuthProvider.LINKEDIN: "LinkedIn",
}


@router.get(
    "/{provider}/authorize",
    response_model=LinkSocialAuthorizeResponse,
    summary="Avvia il collegamento di un provider OAuth all'account corrente",
)
def authorize_social_link(
    provider: OAuthProvider,
    user: AuthenticatedUser,
    google: GoogleOAuthService = Depends(get_google_oauth_service),
    linkedin: LinkedInOAuthService = Depends(get_linkedin_oauth_service),
) -> LinkSocialAuthorizeResponse:
    """Restituisce URL provider e ``state`` (JWT con user id). Il FE reindirizza il browser."""
    label = _PROVIDER_LABELS[provider]
    try:
        if provider is OAuthProvider.GOOGLE:
            payload = google.build_link_authorize_payload(user.id)
        else:
            payload = linkedin.build_link_authorize_payload(user.id)
    except OAuthSignInError as exc:
        raise http_error_from_oauth(exc, provider_label=label)
    return LinkSocialAuthorizeResponse(
        authorization_url=payload.authorization_url,
        state=payload.state,
        provider=provider,
    )


@router.delete(
    "/{provider}",
    response_model=UnlinkSocialAccountResponse,
    summary="Scollega un provider OAuth dall'account corrente",
)
def unlink_social_account(
    provider: OAuthProvider,
    user: AuthenticatedUser,
    db: Session = Depends(get_db),
) -> UnlinkSocialAccountResponse:
    """Rimuove la riga ``auth_social_accounts``. Non consente di restare senza metodi di accesso."""
    social = db.scalar(
        select(AuthSocialAccount).where(
            AuthSocialAccount.user_id == user.id,
            AuthSocialAccount.provider == provider,
        )
    )
    if social is None:
        raise http_error_social_account_not_linked()

    if count_login_methods(db, user, exclude_provider=provider) < 1:
        raise http_error_cannot_unlink_last_login()

    db.delete(social)
    try:
        db.commit()
    except Exception as exc:
        db.rollback()
        raise http_error_unlink_social_account_failed() from exc

    return UnlinkSocialAccountResponse(disconnected=True, provider=provider.value)
