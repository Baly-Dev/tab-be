"""Rimuove i dati personali che restano fuori dal CASCADE di ``auth_users``."""

from __future__ import annotations

import re

from sqlalchemy import Text, cast, or_, select
from sqlalchemy.orm import Session

from admin.models.audit_log import AdminAuditLog
from auth.models.user import AuthUser
from core.models.profile import CoreProfile
from notifications.models.notification import Notification
from services.storage import get_storage_service

_ACTOR_FIELDS = (
    "actor_username",
    "actor_first_name",
    "actor_last_name",
    "actor_avatar_url",
)


def _ilike_contains(value: str) -> str:
    """Pattern ILIKE con ``%`` e ``_`` letterali."""
    escaped = value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return f"%{escaped}%"


def _matches_identity(value: str, username: str, email: str) -> bool:
    lowered = value.strip().lower()
    handle = f"@{username}".lower()
    return lowered == username.lower() or lowered == email.lower() or lowered == handle


def redact_text(text: str, *, username: str, email: str) -> str:
    """Sostituisce email e ``@username`` lasciando intatto il resto della frase."""
    result = text
    if email:
        result = re.sub(re.escape(email), "removed", result, flags=re.IGNORECASE)
    if username:
        result = re.sub(rf"@{re.escape(username)}\b", "@removed", result, flags=re.IGNORECASE)
        if result == username:
            return "removed"
    return result


def redact_payload(value: object, *, user_id: str, username: str, email: str) -> object:
    """Anonimizza snapshot e campi identici a email/username dentro un JSON."""
    if isinstance(value, dict):
        actor_id = str(value.get("actor_id") or "")
        subject_id = str(value.get("user_id") or value.get("target_id") or "")
        about_user = actor_id == user_id or subject_id == user_id
        redacted: dict[object, object] = {}
        for key, item in value.items():
            if about_user and key in _ACTOR_FIELDS:
                redacted[key] = None
                continue
            if (
                key in {"email", "username"}
                and isinstance(item, str)
                and _matches_identity(item, username, email)
            ):
                redacted[key] = "removed"
                continue
            redacted[key] = redact_payload(item, user_id=user_id, username=username, email=email)
        return redacted
    if isinstance(value, list):
        return [
            redact_payload(item, user_id=user_id, username=username, email=email) for item in value
        ]
    if isinstance(value, str):
        if _matches_identity(value, username, email):
            return "removed"
        return redact_text(value, username=username, email=email)
    return value


def erase_retained_personal_data(db: Session, user: AuthUser) -> None:
    """File avatar, snapshot nelle notifiche altrui e identificativi negli audit log."""
    username = str(user.username)
    email = str(user.email)
    user_id = str(user.id)
    _scrub_notifications(db, user_id=user_id, username=username, email=email)
    _scrub_audit_logs(db, user=user, username=username, email=email)
    _delete_avatar_files(db, user)


def _scrub_notifications(db: Session, *, user_id: str, username: str, email: str) -> None:
    rows = db.scalars(
        select(Notification).where(
            or_(
                Notification.payload["actor_id"].astext == user_id,
                cast(Notification.payload, Text).ilike(_ilike_contains(email), escape="\\"),
                cast(Notification.payload, Text).ilike(
                    _ilike_contains(f"@{username}"),
                    escape="\\",
                ),
                cast(Notification.payload, Text).ilike(_ilike_contains(username), escape="\\"),
            )
        )
    ).all()
    for row in rows:
        raw = row.payload if isinstance(row.payload, dict) else {}
        row.payload = redact_payload(raw, user_id=user_id, username=username, email=email)


def _scrub_audit_logs(db: Session, *, user: AuthUser, username: str, email: str) -> None:
    user_id = str(user.id)
    rows = db.scalars(
        select(AdminAuditLog).where(
            or_(
                AdminAuditLog.actor_id == user.id,
                AdminAuditLog.target_id == user_id,
                AdminAuditLog.actor_username == username,
                AdminAuditLog.message.ilike(_ilike_contains(f"@{username}"), escape="\\"),
                cast(AdminAuditLog.payload, Text).ilike(_ilike_contains(email), escape="\\"),
                cast(AdminAuditLog.payload, Text).ilike(_ilike_contains(username), escape="\\"),
            )
        )
    ).all()
    for row in rows:
        row.message = redact_text(str(row.message), username=username, email=email)
        actor_name = str(row.actor_username) if row.actor_username else ""
        same_actor = bool(actor_name) and _matches_identity(actor_name, username, email)
        if row.actor_id == user.id or same_actor:
            row.actor_username = None
        if isinstance(row.payload, dict):
            row.payload = redact_payload(
                row.payload,
                user_id=user_id,
                username=username,
                email=email,
            )


def _delete_avatar_files(db: Session, user: AuthUser) -> None:
    profile = db.get(CoreProfile, user.id)
    storage = get_storage_service()
    if profile is not None and profile.avatar_url:
        storage.delete_if_managed(str(profile.avatar_url))
    storage.delete_prefix(f"avatars/{user.id}")
