"""Schemi risposta profilo pubblico utente."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, Field

from config.constants import ConnectionStatus
from services.storage import PublicMediaUrl


class PublicProfileInterestItem(BaseModel):
    """Interesse visibile sul profilo pubblico."""

    id: uuid.UUID
    name: str


class ViewerConnectionContext(BaseModel):
    """Relazione 1° grado tra viewer autenticato e utente del profilo."""

    connection_id: uuid.UUID
    status: ConnectionStatus
    initiated_by_viewer: bool = Field(
        description="True se il viewer ha inviato la richiesta di connessione.",
    )


class PublicProfileResponse(BaseModel):
    """Profilo pubblico di un utente (solo campi non sensibili + contesto viewer)."""

    id: uuid.UUID
    username: str
    is_self: bool = Field(description="True se il viewer sta guardando il proprio profilo.")
    roles: list[str] = Field(
        description="Ruoli pubblici. Senza connessione include solo il ruolo connector (badge ambassador).",
    )
    interests: list[PublicProfileInterestItem]
    first_name: str
    last_name: str
    bio: str | None = None
    avatar_url: PublicMediaUrl = None
    current_company_name: str | None = None
    current_job_position: str | None = None
    residence_country: str | None = None
    residence_city: str | None = None
    profile_completeness: int = 0
    connection: ViewerConnectionContext | None = Field(
        default=None,
        description="Relazione con il viewer; null se nessuna connessione esiste.",
    )
    mutual_connections_count: int = Field(
        default=0,
        description="Connessioni accettate in comune tra viewer e utente del profilo.",
    )
    connections_count: int = Field(
        default=0,
        description="Totale connessioni accettate (1° grado) dell'utente del profilo.",
    )
    post_counts: int = Field(
        default=0,
        description="Numero di post/opportunity pubblicati dall'utente.",
    )
    profile_visible: bool = Field(
        default=True,
        description="False se il viewer non è connesso (accepted): i dettagli profilo sono omessi.",
    )
    joined_at: datetime
