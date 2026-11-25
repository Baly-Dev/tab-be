"""Application roles stored on ``auth_user_roles``."""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from auth.models.user_role import AuthUserRole
from config.constants import AppRole


def load_user_roles(db: Session, user_id: uuid.UUID) -> list[str]:
    """Role values for ``user_id`` (database order)."""
    rows = db.scalars(select(AuthUserRole.role).where(AuthUserRole.user_id == user_id)).all()
    return [r.value for r in rows]


def ensure_member_role(db: Session, user_id: uuid.UUID) -> None:
    """Assign ``member`` when the user has no member role yet."""
    existing = db.scalar(
        select(AuthUserRole.id).where(
            AuthUserRole.user_id == user_id,
            AuthUserRole.role == AppRole.MEMBER,
        )
    )
    if existing is None:
        db.add(AuthUserRole(user_id=user_id, role=AppRole.MEMBER))
