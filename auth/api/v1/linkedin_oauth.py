"""LinkedIn OAuth: authorize, callback redirect e sign-in JSON."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query, status
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession

from auth.errors.oauth_errors import OAuthSignInError, OAuthStateError, http_error_from_oauth
from auth.schemas.linkedin_oauth import (
    LinkedInAuthorizeResponse,
    LinkedInSignInRequest,
    LinkedInSignInResponse,
)
from auth.utils.oauth import decode_oauth_state, oauth_link_error_code
from auth.utils.rate_limit import require_ip_limit
from config.db import get_async_db
from services.linkedin_oauth import (
    TOKEN_TYP_LINKEDIN_OAUTH_LINK,
    TOKEN_TYP_LINKEDIN_OAUTH_STATE,
    LinkedInOAuthService,
    get_linkedin_oauth_service,
)

router = APIRouter()
_PROVIDER_LABEL = "LinkedIn"


@router.get("/linkedin/authorize", response_model=LinkedInAuthorizeResponse)
async def linkedin_authorize(
    linkedin: LinkedInOAuthService = Depends(get_linkedin_oauth_service),
    _: None = Depends(require_ip_limit("oauth")),
) -> LinkedInAuthorizeResponse:
    """Restituisce URL LinkedIn e ``state`` (CSRF). Il FE reindirizza a ``authorization_url``."""
    try:
        payload = linkedin.build_authorize_payload()
    except OAuthSignInError as exc:
        raise http_error_from_oauth(exc, provider_label=_PROVIDER_LABEL)
    return LinkedInAuthorizeResponse(
        authorization_url=payload.authorization_url,
        state=payload.state,
    )


@router.get("/linkedin/callback")
async def linkedin_callback(
    code: str = Query(min_length=1),
    state: str = Query(min_length=10),
    db: AsyncSession = Depends(get_async_db),
    linkedin: LinkedInOAuthService = Depends(get_linkedin_oauth_service),
    _: None = Depends(require_ip_limit("oauth")),
) -> RedirectResponse:
    """Callback LinkedIn (redirect URI backend): sign-in o link da Settings."""
    state_typ: str | None = None
    try:
        state_typ = str(decode_oauth_state(state).get("typ") or "")
        if state_typ == TOKEN_TYP_LINKEDIN_OAUTH_LINK:
            await linkedin.link_with_code(db, code=code, state=state)
            redirect_url = linkedin.build_frontend_link_redirect_url()
        elif state_typ == TOKEN_TYP_LINKEDIN_OAUTH_STATE:
            result = await linkedin.sign_in_with_code(db, code=code, state=state)
            redirect_url = await linkedin.build_frontend_redirect_url(result)
        else:
            raise OAuthStateError("Invalid OAuth state type")
    except OAuthSignInError as exc:
        if state_typ == TOKEN_TYP_LINKEDIN_OAUTH_LINK:
            return RedirectResponse(
                url=linkedin.build_frontend_link_redirect_url(error=oauth_link_error_code(exc)),
                status_code=status.HTTP_302_FOUND,
            )
        raise http_error_from_oauth(exc, provider_label=_PROVIDER_LABEL)
    return RedirectResponse(url=redirect_url, status_code=status.HTTP_302_FOUND)


@router.post("/linkedin/sign-in", response_model=LinkedInSignInResponse)
async def linkedin_sign_in(
    body: LinkedInSignInRequest,
    db: AsyncSession = Depends(get_async_db),
    linkedin: LinkedInOAuthService = Depends(get_linkedin_oauth_service),
    _: None = Depends(require_ip_limit("oauth")),
) -> LinkedInSignInResponse:
    """Sign-in con code + state (JSON)."""
    try:
        result = await linkedin.sign_in_with_code(db, code=body.code, state=body.state)
    except OAuthSignInError as exc:
        raise http_error_from_oauth(exc, provider_label=_PROVIDER_LABEL)
    return LinkedInSignInResponse(
        oauth_status=result.oauth_status,
        **result.token_response.model_dump(),
    )
