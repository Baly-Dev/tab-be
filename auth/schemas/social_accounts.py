"""Schemi gestione account OAuth collegati (Settings)."""

from __future__ import annotations

from pydantic import BaseModel, Field

from config import OAuthProvider


class UnlinkSocialAccountResponse(BaseModel):
    disconnected: bool = True
    provider: str = Field(description="Provider scollegato (google | linkedin).")


class LinkSocialAuthorizeResponse(BaseModel):
    """Avvio flusso di collegamento: il FE reindirizza a ``authorization_url``."""

    authorization_url: str
    state: str
    provider: OAuthProvider
