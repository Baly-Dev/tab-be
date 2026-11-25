"""Lettura ruoli applicativi da ``core_user_roles``."""

from __future__ import annotations

import uuid
from collections.abc import Iterable

from sqlalchemy import select
from sqlalchemy.orm import Session

from config.constants import AppRole
from core.models.user_role import CoreUserRole

SIGNUP_INVITE_ROLES = frozenset({AppRole.CONNECTOR, AppRole.ADMIN, AppRole.SUPER_ADMIN})
_SIGNUP_INVITE_ROLE_VALUES = frozenset(role.value for role in SIGNUP_INVITE_ROLES)


def load_user_roles(db: Session, user_id: uuid.UUID) -> list[str]:
    """Ruoli dell'utente come stringhe ``AppRole.value`` (ordine DB)."""
    rows = db.scalars(select(CoreUserRole.role).where(CoreUserRole.user_id == user_id)).all()
    return [r.value for r in rows]


def public_identity_roles(roles: list[str]) -> list[str]:
    """Ruoli visibili anche senza connessione (es. badge ambassador)."""
    return [role for role in roles if role == AppRole.CONNECTOR.value]


def can_invite_to_platform(roles: list[str]) -> bool:
    """True se connector, admin o super_admin (link invito iscrizione)."""
    return any(role in _SIGNUP_INVITE_ROLE_VALUES for role in roles)


def load_connector_user_ids(db: Session, user_ids: Iterable[uuid.UUID]) -> set[uuid.UUID]:
    """Sottoinsieme di ``user_ids`` con ruolo ``connector``."""
    ids = list(user_ids)
    if not ids:
        return set()
    rows = db.scalars(
        select(CoreUserRole.user_id).where(
            CoreUserRole.user_id.in_(ids),
            CoreUserRole.role == AppRole.CONNECTOR,
        ),
    ).all()
    return set(rows)
