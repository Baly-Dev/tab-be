"""Schemi API ricerca membri."""

from __future__ import annotations

import uuid

from pydantic import BaseModel, Field

from config.constants import ConnectionStatus
from services.storage import PublicMediaUrl


class MemberSearchItem(BaseModel):
    """Risultato leggero per search bar / autocomplete."""

    id: uuid.UUID
    username: str
    first_name: str
    last_name: str
    avatar_url: PublicMediaUrl = None
    current_job_position: str | None = None
    residence_city: str | None = None
    connection_status: ConnectionStatus | None = Field(
        default=None,
        description="Relazione con il viewer; null se nessuna connessione.",
    )
    is_connector: bool = Field(
        default=False,
        description="True se l'utente ha ruolo connector (profilo ambassador).",
    )


class MemberSearchResponse(BaseModel):
    """Lista membri compatibili con la query."""

    query: str
    items: list[MemberSearchItem]
    total: int
