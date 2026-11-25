"""Schemi connessioni console admin."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, Field, model_validator

from config.constants import ConnectionStatus
from services.storage import PublicMediaUrl


class AdminPeerIdentity(BaseModel):
    """Identità minima di un capo della connessione."""

    id: uuid.UUID
    username: str
    first_name: str | None = None
    last_name: str | None = None
    avatar_url: PublicMediaUrl = None
    roles: list[str] = Field(default_factory=list)


class AdminConnectionItem(BaseModel):
    """Connessione 1° grado vista staff."""

    id: uuid.UUID
    status: ConnectionStatus
    initiated_by_id: uuid.UUID
    created_at: datetime
    updated_at: datetime
    user_low: AdminPeerIdentity
    user_high: AdminPeerIdentity


class AdminConnectionListResponse(BaseModel):
    """Pagina elenco connessioni."""

    items: list[AdminConnectionItem]
    total: int
    limit: int
    offset: int


class CreateAdminConnectionRequest(BaseModel):
    """Crea o aggiorna una relazione tra due utenti."""

    user_a_id: uuid.UUID
    user_b_id: uuid.UUID
    status: ConnectionStatus = ConnectionStatus.ACCEPTED

    @model_validator(mode="after")
    def distinct_users(self) -> CreateAdminConnectionRequest:
        if self.user_a_id == self.user_b_id:
            msg = "user_a_id and user_b_id must be different"
            raise ValueError(msg)
        return self


class UpdateAdminConnectionRequest(BaseModel):
    """Cambio stato connessione esistente."""

    status: ConnectionStatus
