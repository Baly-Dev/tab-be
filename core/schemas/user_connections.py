"""Elenco connessioni accepted visibili sul profilo di un utente."""

from __future__ import annotations

import uuid

from pydantic import BaseModel, Field

from core.schemas.public_profile import ViewerConnectionContext
from services.storage import PublicMediaUrl


class ProfileConnectionPeerResponse(BaseModel):
    """Contatto accepted del profilo, con relazione rispetto al viewer."""

    id: uuid.UUID
    username: str
    first_name: str | None = None
    last_name: str | None = None
    avatar_url: PublicMediaUrl = None
    is_self: bool = Field(description="True se questo contatto è il viewer.")
    connection: ViewerConnectionContext | None = Field(
        default=None,
        description="Relazione tra viewer e questo contatto; null se assente o se is_self.",
    )
    is_connector: bool = Field(
        default=False,
        description="True se l'utente ha ruolo connector (profilo ambassador).",
    )


class ProfileConnectionsListResponse(BaseModel):
    """Connessioni accepted dell'utente del profilo."""

    items: list[ProfileConnectionPeerResponse]
    total: int
