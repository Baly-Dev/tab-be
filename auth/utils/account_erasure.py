"""Rimuove i dati personali che restano fuori dal CASCADE di ``auth_users``."""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from auth.models.user import AuthUser
from core.models.profile import CoreProfile
from services.storage import get_storage_service


async def erase_retained_personal_data(db: AsyncSession, user: AuthUser) -> None:
    """File avatar in storage gestito (notifiche/audit arriveranno con i nuovi moduli)."""
    await _delete_avatar_files(db, user)


async def _delete_avatar_files(db: AsyncSession, user: AuthUser) -> None:
    profile = await db.get(CoreProfile, user.id)
    storage = get_storage_service()
    if profile is not None and profile.avatar_url:
        storage.delete_if_managed(str(profile.avatar_url))
    storage.delete_prefix(f"avatars/{user.id}")