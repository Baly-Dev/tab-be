"""Schemi API LinkedIn OAuth."""

from pydantic import BaseModel, Field

from auth.schemas.login import TokenResponse


class LinkedInAuthorizeResponse(BaseModel):
    """Avvio flusso: redirect del browser verso ``authorization_url`` (conservare ``state``)."""

    authorization_url: str
    state: str


class LinkedInSignInRequest(BaseModel):
    """Alternativa al redirect browser: FE invia code + state dopo callback LinkedIn."""

    code: str = Field(min_length=1, description="Authorization code da LinkedIn.")
    state: str = Field(min_length=10, description="State restituito da GET /linkedin/authorize.")


class LinkedInSignInResponse(TokenResponse):
    """Stessi campi del login + ``oauth_status`` (new_user | existing_user)."""

    oauth_status: str = Field(description="new_user | existing_user")
