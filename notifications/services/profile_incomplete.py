"""Notifica in-app se il profilo manca di campi comuni a signup e edit."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified

from auth.models.user import AuthUser
from config import UserStatus
from config.constants import NotificationType
from core.models.profile import CoreProfile
from core.models.user_interest import CoreUserInterest
from notifications.models.notification import Notification
from notifications.services.notify import notify

PROFILE_INCOMPLETE_DEDUP = "profile_incomplete"
PROFILE_EDIT_DEEP_LINK = "/settings/profile/edit"

# Intersezione wizard signup ∩ form di edit (LinkedIn/università esclusi: solo edit).
_NUDGE_PROFILE_FIELDS = (
    "residence_country",
    "residence_city",
    "current_job_position",
    "current_company_name",
    "bio",
    "avatar_url",
)


def missing_profile_fields(db: Session, user_id: uuid.UUID) -> list[str]:
    """Campi vuoti tra quelli chiesti in registrazione e in modifica profilo."""
    profile = db.get(CoreProfile, user_id)
    missing: list[str] = []
    if profile is None:
        missing.extend(_NUDGE_PROFILE_FIELDS)
    else:
        for key in _NUDGE_PROFILE_FIELDS:
            value = getattr(profile, key, None)
            if value is None or (isinstance(value, str) and not value.strip()):
                missing.append(key)

    has_interest = (
        db.scalar(
            select(CoreUserInterest.interest_id).where(CoreUserInterest.user_id == user_id).limit(1)
        )
        is not None
    )
    if not has_interest:
        missing.append("interests")
    return missing


def sync_profile_incomplete_notification(db: Session, user: AuthUser) -> None:
    """All'accesso: crea/riapre la notifica se il profilo è incompleto, altrimenti la segna letta.

    Non committa: il caller possiede la transazione.
    """
    if user.status != UserStatus.ACTIVE:
        return

    missing = missing_profile_fields(db, user.id)
    existing = db.scalar(
        select(Notification).where(
            Notification.user_id == user.id,
            Notification.type == NotificationType.PROFILE_INCOMPLETE,
            Notification.dedup_key == PROFILE_INCOMPLETE_DEDUP,
        )
    )

    if not missing:
        if existing is not None and not existing.read:
            existing.read = True
            existing.read_at = datetime.now(UTC)
            db.add(existing)
        return

    payload = {
        "deep_link": PROFILE_EDIT_DEEP_LINK,
        "entity_type": "profile",
        "missing_fields": missing,
    }
    if existing is None:
        notify(
            db,
            user_id=user.id,
            notification_type=NotificationType.PROFILE_INCOMPLETE,
            payload=payload,
            dedup_key=PROFILE_INCOMPLETE_DEDUP,
        )
        return

    existing.payload = payload
    flag_modified(existing, "payload")
    existing.read = False
    existing.read_at = None
    db.add(existing)
