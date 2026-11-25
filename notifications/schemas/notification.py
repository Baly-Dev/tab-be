"""Schemi API inbox notifiche."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel

from config.constants import NotificationType
from services.storage import PublicMediaUrl


class NotificationPayload(BaseModel):
    """Contratto payload JSONB (i client localizzano dal ``type``)."""

    model_config = {"extra": "allow"}

    actor_id: uuid.UUID | None = None
    actor_username: str | None = None
    actor_first_name: str | None = None
    actor_last_name: str | None = None
    actor_avatar_url: PublicMediaUrl = None
    entity_type: str | None = None
    entity_id: str | None = None
    deep_link: str = "/notifications"
    event_title: str | None = None
    event_slug: str | None = None
    registration_status: str | None = None
    missing_fields: list[str] | None = None


class NotificationResponse(BaseModel):
    """Notifica inbox rispetto al destinatario autenticato."""

    id: uuid.UUID
    type: NotificationType
    payload: NotificationPayload
    read: bool
    read_at: datetime | None = None
    created_at: datetime


class NotificationListResponse(BaseModel):
    """Pagina inbox, più recenti prima."""

    items: list[NotificationResponse]
    total: int
    unread_count: int
    limit: int
    offset: int


class UnreadCountResponse(BaseModel):
    """Badge header / native."""

    unread_count: int


class MarkAllReadResponse(BaseModel):
    """Esito mark-as-read massivo."""

    updated: int
