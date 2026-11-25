"""Schemi registro console."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel


class AdminAuditLogItem(BaseModel):
    """Riga di log strutturata."""

    id: uuid.UUID
    created_at: datetime
    module: str
    action: str
    level: str
    actor_id: uuid.UUID | None = None
    actor_username: str | None = None
    target_type: str | None = None
    target_id: str | None = None
    message: str
    payload: dict[str, Any] | None = None


class AdminAuditModuleCount(BaseModel):
    """Conteggio righe per modulo."""

    module: str
    count: int


class AdminAuditLogListResponse(BaseModel):
    """Pagina registro + conteggi modulo."""

    items: list[AdminAuditLogItem]
    total: int
    limit: int
    offset: int
    modules: list[AdminAuditModuleCount]
