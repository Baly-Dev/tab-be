"""Lettura ruoli applicativi da ``core_user_roles``."""

from __future__ import annotations

import uuid
from collections.abc import Iterable

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from config.constants import AppRole
from core.models.user_role import CoreUserRole

SIGNUP_INVITE_ROLES = frozenset({AppRole.PROFESSIONAL, AppRole.ADMIN, AppRole.SUPER_ADMIN})
_SIGNUP_INVITE_ROLE_VALUES = frozenset(role.value for role in SIGNUP_INVITE_ROLES)


async def load_user_roles(db: AsyncSession, user_id: uuid.UUID) -> list[str]:
    """Ruoli dell'utente come stringhe ``AppRole.value`` (ordine DB)."""
    rows = (await db.scalars(select(CoreUserRole.role).where(CoreUserRole.user_id == user_id))).all()
    return [r.value for r in rows]


def public_identity_roles(roles: list[str]) -> list[str]:
    """Nessun badge pubblico sul profilo. Host non è un ruolo account."""
    _ = roles
    return []


def can_invite_to_platform(roles: list[str]) -> bool:
    """True se professional, admin o super_admin (link invito iscrizione)."""
    return any(role in _SIGNUP_INVITE_ROLE_VALUES for role in roles)


async def load_user_ids_with_role(
    db: AsyncSession,
    user_ids: Iterable[uuid.UUID],
    role: AppRole,
) -> set[uuid.UUID]:
    """Sottoinsieme di ``user_ids`` che ha ``role``."""
    ids = list(user_ids)
    if not ids:
        return set()
    rows = (
        await db.scalars(
            select(CoreUserRole.user_id).where(
                CoreUserRole.user_id.in_(ids),
                CoreUserRole.role == role,
            )
        )
    ).all()
    return set(rows)