"""Lettura e stato letto dell'inbox."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from config.constants import NotificationType
from notifications.errors import NotificationNotFoundError
from notifications.models.notification import Notification
from notifications.schemas.notification import NotificationPayload, NotificationResponse

# Richieste di connessione: badge sulla voce Rete, non nell'inbox generale.
_INBOX_HIDDEN_TYPES = (NotificationType.CONNECTION_REQUEST,)


def _inbox_filters(user_id: uuid.UUID, *, unread_only: bool = False) -> list:
    filters = [
        Notification.user_id == user_id,
        Notification.type.notin_(_INBOX_HIDDEN_TYPES),
    ]
    if unread_only:
        filters.append(Notification.read.is_(False))
    return filters


def list_notifications(
    db: Session,
    user_id: uuid.UUID,
    *,
    limit: int,
    offset: int,
    unread_only: bool = False,
) -> tuple[list[Notification], int, int]:
    """Inbox paginata (created_at DESC) + totali. Esclude le richieste di connessione."""
    filters = _inbox_filters(user_id, unread_only=unread_only)

    total = int(
        db.scalar(select(func.count()).select_from(Notification).where(*filters)) or 0
    )
    unread_count = count_unread(db, user_id)
    rows = list(
        db.scalars(
            select(Notification)
            .where(*filters)
            .order_by(Notification.created_at.desc())
            .limit(limit)
            .offset(offset)
        ).all()
    )
    return rows, total, unread_count


def count_unread(db: Session, user_id: uuid.UUID) -> int:
    """Conteggio badge inbox generale (senza richieste di connessione)."""
    value = db.scalar(
        select(func.count())
        .select_from(Notification)
        .where(*_inbox_filters(user_id, unread_only=True))
    )
    return int(value or 0)


def mark_read(db: Session, user_id: uuid.UUID, notification_id: uuid.UUID) -> Notification:
    """Segna letta una notifica del destinatario. Idempotente se già letta."""
    row = db.get(Notification, notification_id)
    if row is None or row.user_id != user_id:
        raise NotificationNotFoundError
    if not row.read:
        row.read = True
        row.read_at = datetime.now(UTC)
        db.add(row)
        db.commit()
        db.refresh(row)
    return row


def mark_all_read(db: Session, user_id: uuid.UUID) -> int:
    """Segna lette tutte le non lette visibili in inbox. Restituisce quante ne ha aggiornate."""
    now = datetime.now(UTC)
    result = db.execute(
        update(Notification)
        .where(*_inbox_filters(user_id, unread_only=True))
        .values(read=True, read_at=now)
    )
    db.commit()
    return int(result.rowcount or 0)


def delete_notification(db: Session, user_id: uuid.UUID, notification_id: uuid.UUID) -> None:
    """Elimina una notifica del destinatario."""
    row = db.get(Notification, notification_id)
    if row is None or row.user_id != user_id:
        raise NotificationNotFoundError
    db.delete(row)
    db.commit()


def to_response(row: Notification) -> NotificationResponse:
    """Mappa ORM → schema API."""
    raw = row.payload if isinstance(row.payload, dict) else {}
    return NotificationResponse(
        id=row.id,
        type=row.type,
        payload=NotificationPayload.model_validate(raw),
        read=bool(row.read),
        read_at=row.read_at,
        created_at=row.created_at,
    )
