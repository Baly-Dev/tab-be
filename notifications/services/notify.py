"""Punto unico di scrittura inbox. Non committa: il caller possiede la transazione."""

from __future__ import annotations

import logging
import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from config.constants import NotificationType
from notifications.models.notification import Notification

logger = logging.getLogger(__name__)


def notify(
    db: Session,
    *,
    user_id: uuid.UUID,
    notification_type: NotificationType,
    payload: dict[str, Any],
    dedup_key: str | None = None,
) -> Notification | None:
    """Inserisce una riga inbox. Idempotente se ``dedup_key`` è già presente.

    Non invia email/push: i canali restano ai moduli di dominio (o a un worker futuro).
    Non committa: il caller possiede la transazione.
    """
    key = dedup_key.strip() if dedup_key else None
    if key:
        existing = _find_by_dedup(
            db,
            user_id=user_id,
            notification_type=notification_type,
            dedup_key=key,
        )
        if existing is not None:
            return existing

    row = Notification(
        user_id=user_id,
        type=notification_type,
        payload=dict(payload),
        read=False,
        dedup_key=key,
    )
    try:
        with db.begin_nested():
            db.add(row)
            db.flush()
    except IntegrityError:
        existing = (
            _find_by_dedup(
                db,
                user_id=user_id,
                notification_type=notification_type,
                dedup_key=key,
            )
            if key
            else None
        )
        if existing is not None:
            return existing
        logger.exception(
            "notifications.notify integrity_error user_id=%s type=%s",
            user_id,
            notification_type.value,
        )
        return None

    logger.info(
        "notifications.created id=%s user_id=%s type=%s",
        row.id,
        user_id,
        notification_type.value,
    )
    return row


def _find_by_dedup(
    db: Session,
    *,
    user_id: uuid.UUID,
    notification_type: NotificationType,
    dedup_key: str,
) -> Notification | None:
    return db.scalar(
        select(Notification).where(
            Notification.user_id == user_id,
            Notification.type == notification_type,
            Notification.dedup_key == dedup_key,
        )
    )
