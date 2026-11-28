"""Permessi applicativi centralizzati (RBAC per ruolo).

Aggiungere nuovi valori in ``Permission`` e mapparli in ``ROLE_PERMISSIONS``.
``super_admin`` riceve automaticamente tutti i permessi definiti nell'enum.
"""

from __future__ import annotations

import enum
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from config.constants import AppRole
from core.utils.roles import load_user_roles


class Permission(str, enum.Enum):
    """Capability granulari; usate da route e service layer."""

    MEMBERS_SEARCH = "members.search"
    ADMIN_READ = "admin.read"
    ADMIN_WRITE = "admin.write"
    ADMIN_LOGS = "admin.logs"


_ALL_PERMISSIONS = frozenset(Permission)

ROLE_PERMISSIONS: dict[AppRole, frozenset[Permission]] = {
    AppRole.SUPER_ADMIN: _ALL_PERMISSIONS,
    AppRole.ADMIN: frozenset(
        {
            Permission.MEMBERS_SEARCH,
            Permission.ADMIN_READ,
        }
    ),
    AppRole.PROFESSIONAL: frozenset({Permission.MEMBERS_SEARCH}),
}


def permissions_for_roles(role_names: list[str]) -> set[Permission]:
    """Unione permessi per una lista di ruoli (stringhe da DB/JWT)."""
    granted: set[Permission] = set()
    for name in role_names:
        try:
            role = AppRole(name)
        except ValueError:
            continue
        granted |= ROLE_PERMISSIONS.get(role, frozenset())
    return granted


async def user_has_permission(db: AsyncSession, user_id: uuid.UUID, permission: Permission) -> bool:
    """True se almeno un ruolo dell'utente concede ``permission``."""
    roles = await load_user_roles(db, user_id)
    return permission in permissions_for_roles(roles)


async def user_has_any_permission(
    db: AsyncSession,
    user_id: uuid.UUID,
    permissions: frozenset[Permission],
) -> bool:
    """True se l'utente ha almeno uno dei permessi indicati."""
    roles = await load_user_roles(db, user_id)
    user_perms = permissions_for_roles(roles)
    return bool(user_perms & permissions)