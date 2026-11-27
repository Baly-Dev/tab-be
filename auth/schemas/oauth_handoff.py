"""Exchange a one-time OAuth browser handoff for the login token pair."""

from pydantic import BaseModel, Field

from auth.schemas.login import TokenResponse


class OAuthHandoffRequest(BaseModel):
    handoff: str = Field(min_length=32, max_length=128)


class OAuthHandoffResponse(TokenResponse):
    """Same body as login, plus whether the OAuth account was new."""

    oauth_status: str = Field(description="new_user | existing_user")
