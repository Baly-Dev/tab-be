"""Schemi API connessioni utente."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, Field

from config.constants import ConnectionStatus
from services.storage import PublicMediaUrl


class CreateConnectionRequest(BaseModel):
    """Richiesta connessione verso un altro utente."""

    target_user_id: uuid.UUID = Field(description="UUID dell'utente da connettere.")


class ConnectionPeerResponse(BaseModel):
    """Riepilogo utente collegato."""

    id: uuid.UUID
    username: str
    first_name: str | None = None
    last_name: str | None = None
    avatar_url: PublicMediaUrl = None
    is_connector: bool = False


class ConnectionResponse(BaseModel):
    """Connessione 1° grado rispetto al viewer autenticato."""

    id: uuid.UUID
    status: ConnectionStatus
    initiated_by_me: bool
    peer: ConnectionPeerResponse
    created_at: datetime
    updated_at: datetime


class ConnectionListResponse(BaseModel):
    """Lista connessioni dell'utente autenticato."""

    items: list[ConnectionResponse]
    total: int
