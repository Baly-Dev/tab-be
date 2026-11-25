"""Schemi console per i job automatici."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class AdminBatchJobField(BaseModel):
    """Parametro mostrato e modificabile in console."""

    key: str
    label: str
    help: str
    minimum: int
    maximum: int
    value: int


class AdminBatchJobRunItem(BaseModel):
    """Esecuzione registrata."""

    id: uuid.UUID
    started_at: datetime
    finished_at: datetime
    status: str
    sent_count: int
    trigger: str
    message: str
    error: str | None = None
    actor_username: str | None = None


class AdminBatchJobItem(BaseModel):
    """Job del catalogo con stato e storico recente."""

    key: str
    title: str
    description: str
    enabled: bool
    interval_seconds: int
    fields: list[AdminBatchJobField]
    last_started_at: datetime | None = None
    last_finished_at: datetime | None = None
    last_status: str | None = None
    last_sent_count: int | None = None
    last_error: str | None = None
    runs: list[AdminBatchJobRunItem]


class AdminBatchJobListResponse(BaseModel):
    """Elenco job automatici."""

    jobs: list[AdminBatchJobItem]


class UpdateAdminBatchJobRequest(BaseModel):
    """Nuovo stato di un job."""

    enabled: bool
    interval_seconds: int = Field(ge=60, le=86_400)
    config: dict[str, int] = Field(default_factory=dict)
