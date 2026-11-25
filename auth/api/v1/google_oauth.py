"""Google OAuth: authorize, callback redirect e sign-in JSON."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query, status
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from auth.errors.oauth_errors import OAuthSignInError, OAuthStateError, http_error_from_oauth
from auth.schemas.google_oauth import (
    GoogleAuthorizeResponse,
    GoogleSignInRequest,
    GoogleSignInResponse,
)
from auth.utils.oauth import decode_oauth_state, oauth_link_error_code
from config.db.session import get_db
from services.google_oauth import (
    TOKEN_TYP_GOOGLE_OAUTH_LINK,
    TOKEN_TYP_GOOGLE_OAUTH_STATE,
    GoogleOAuthService,
    get_google_oauth_service,
)

router = APIRouter()
_PROVIDER_LABEL = "Google"


@router.get("/google/authorize", response_model=GoogleAuthorizeResponse)
def google_authorize(
    google: GoogleOAuthService = Depends(get_google_oauth_service),
) -> GoogleAuthorizeResponse:
    """Restituisce URL Google e ``state`` (CSRF). Il FE reindirizza l'utente a ``authorization_url``."""
    try:
        payload = google.build_authorize_payload()
    except OAuthSignInError as exc:
        raise http_error_from_oauth(exc, provider_label=_PROVIDER_LABEL)
    return GoogleAuthorizeResponse(
        authorization_url=payload.authorization_url,
        state=payload.state,
    )


@router.get("/google/callback")
def google_callback(
    code: str = Query(min_length=1),
    state: str = Query(min_length=10),
    db: Session = Depends(get_db),
    google: GoogleOAuthService = Depends(get_google_oauth_service),
) -> RedirectResponse:
    """Callback Google (redirect URI backend): sign-in o link da Settings."""
    state_typ: str | None = None
    try:
        state_typ = str(decode_oauth_state(state).get("typ") or "")
        if state_typ == TOKEN_TYP_GOOGLE_OAUTH_LINK:
            google.link_with_code(db, code=code, state=state)
            redirect_url = google.build_frontend_link_redirect_url()
        elif state_typ == TOKEN_TYP_GOOGLE_OAUTH_STATE:
            result = google.sign_in_with_code(db, code=code, state=state)
            redirect_url = google.build_frontend_redirect_url(result)
        else:
            raise OAuthStateError("Invalid OAuth state type")
    except OAuthSignInError as exc:
        if state_typ == TOKEN_TYP_GOOGLE_OAUTH_LINK:
            return RedirectResponse(
                url=google.build_frontend_link_redirect_url(error=oauth_link_error_code(exc)),
                status_code=status.HTTP_302_FOUND,
            )
        raise http_error_from_oauth(exc, provider_label=_PROVIDER_LABEL)
    return RedirectResponse(url=redirect_url, status_code=status.HTTP_302_FOUND)


@router.post("/google/sign-in", response_model=GoogleSignInResponse)
def google_sign_in(
    body: GoogleSignInRequest,
    db: Session = Depends(get_db),
    google: GoogleOAuthService = Depends(get_google_oauth_service),
) -> GoogleSignInResponse:
    """Sign-in con code + state (JSON, senza redirect browser verso il FE)."""
    try:
        result = google.sign_in_with_code(db, code=body.code, state=body.state)
    except OAuthSignInError as exc:
        raise http_error_from_oauth(exc, provider_label=_PROVIDER_LABEL)
    return GoogleSignInResponse(
        oauth_status=result.oauth_status,
        **result.token_response.model_dump(),
    )
