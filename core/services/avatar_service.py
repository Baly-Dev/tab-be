"""Upload e sostituzione avatar profilo."""

from __future__ import annotations

import asyncio
import uuid

from fastapi import UploadFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from auth.models.user import AuthUser
from core.errors.profile_errors import http_error_for_own_profile_missing
from core.models.profile import CoreProfile
from core.models.user_interest import CoreUserInterest
from core.schemas.me import MeResponse
from core.utils.me import build_me_response
from services.images import process_avatar
from services.storage import get_storage_service
from services.uploads import read_upload_bytes

MAX_AVATAR_BYTES = 5 * 1024 * 1024
MAX_AVATAR_MB = 5


async def set_avatar_from_upload(db: AsyncSession, user: AuthUser, file: UploadFile) -> MeResponse:
    """Processa l'immagine, la salva e aggiorna ``core_profiles.avatar_url``."""
    profile = await db.get(CoreProfile, user.id)
    if profile is None:
        raise http_error_for_own_profile_missing()

    raw = await asyncio.to_thread(
        read_upload_bytes, file, max_bytes=MAX_AVATAR_BYTES, max_mb=MAX_AVATAR_MB
    )
    processed = await asyncio.to_thread(process_avatar, raw)
    key = f"avatars/{user.id}/{uuid.uuid4()}.webp"
    storage = get_storage_service()
    url = await asyncio.to_thread(storage.put_bytes, key, processed, "image/webp")

    previous = str(profile.avatar_url).strip() if profile.avatar_url else None
    profile.avatar_url = url
    has_interests = (
        await db.scalar(
            select(CoreUserInterest.interest_id).where(CoreUserInterest.user_id == user.id).limit(1)
        )
        is not None
    )
    profile.refresh_completeness(has_interests=has_interests)
    db.add(profile)
    await db.commit()

    if previous and previous != url:
        await asyncio.to_thread(storage.delete_if_managed, previous)

    return await build_me_response(db, user)
