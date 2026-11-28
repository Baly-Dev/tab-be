"""Stato registrazione / wizard onboarding (caricamento DB in utils)."""

from __future__ import annotations

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from auth.models.user import AuthUser
from core.models.profile import CoreProfile


async def is_registration_complete(db: AsyncSession, user_id: uuid.UUID) -> bool:
    """True se l'account è operativo (wizard/verifica fatti, o utente importato WP)."""
    user = await db.get(AuthUser, user_id)
    if user is None:
        return False
    profile = await db.get(CoreProfile, user_id)
    return user.is_registration_complete(profile)