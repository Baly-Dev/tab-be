"""POST /oauth/handoff — redeem the fragment code from the OAuth browser redirect."""

from __future__ import annotations

from fastapi import APIRouter

from auth.errors.oauth_errors import (
    OAuthHandoffUnavailableError,
    http_error_invalid_oauth_handoff,
    http_error_oauth_handoff_unavailable,
)
from auth.schemas.oauth_handoff import OAuthHandoffRequest, OAuthHandoffResponse
from auth.utils.oauth_handoff import consume_oauth_handoff

router = APIRouter()


@router.post("/oauth/handoff", response_model=OAuthHandoffResponse)
def exchange_oauth_handoff(body: OAuthHandoffRequest) -> OAuthHandoffResponse:
    """Single use. The code arrives in the URL fragment, then this body."""
    try:
        payload = consume_oauth_handoff(body.handoff.strip())
    except OAuthHandoffUnavailableError:
        raise http_error_oauth_handoff_unavailable() from None
    if payload is None:
        raise http_error_invalid_oauth_handoff()
    return OAuthHandoffResponse.model_validate(payload)
