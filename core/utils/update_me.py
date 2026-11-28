"""Aggiornamento profilo proprio (PATCH /core/me)."""

from __future__ import annotations

import uuid

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from auth.models.user import AuthUser
from core.errors.profile_errors import (
    http_error_empty_update,
    http_error_for_own_profile_missing,
    http_error_invalid_interest_ids,
)
from core.models.interest import CoreInterest
from core.models.profile import CoreProfile
from core.models.user_interest import CoreUserInterest
from core.schemas.me import MeResponse
from core.schemas.me_update import UpdateMeRequest
from core.utils.me import build_me_response

_PROFILE_PATCH_FIELDS = (
    "first_name",
    "last_name",
    "birth_date",
    "gender",
    "residence_country",
    "residence_city",
    "office_city",
    "office_neighborhood",
    "bio",
    "avatar_url",
    "current_company_name",
    "current_job_position",
    "linkedin_url",
    "preferred_cuisine",
    "preferred_price_band",
    "max_distance_meters",
    "dietary_notes",
    "prefers_meal_vouchers",
)


async def update_me(db: AsyncSession, user: AuthUser, body: UpdateMeRequest) -> MeResponse:
    """Applica patch al profilo (e interessi se presenti) e restituisce ``MeResponse``."""
    payload = body.model_dump(exclude_unset=True)
    if not payload:
        raise http_error_empty_update()

    profile = await db.get(CoreProfile, user.id)
    if profile is None:
        raise http_error_for_own_profile_missing()

    interest_ids: list[uuid.UUID] | None = payload.pop("interest_ids", None)

    patch = {key: payload[key] for key in _PROFILE_PATCH_FIELDS if key in payload}
    profile.apply_patch(patch)

    if interest_ids is not None:
        await _replace_interests(db, user.id, interest_ids)

    has_interests = (
        await db.scalar(
            select(CoreUserInterest.interest_id).where(CoreUserInterest.user_id == user.id).limit(1)
        )
        is not None
    )
    profile.refresh_completeness(has_interests=has_interests)
    db.add(profile)
    await db.commit()

    return await build_me_response(db, user)


async def _replace_interests(db: AsyncSession, user_id: uuid.UUID, interest_ids: list[uuid.UUID]) -> None:
    """Valida e sostituisce gli interessi dell'utente (lista vuota = nessuno)."""
    if interest_ids:
        found = (await db.scalars(
            select(CoreInterest.id).where(
                CoreInterest.id.in_(interest_ids),
                CoreInterest.is_active.is_(True),
            )
        )).all()
        if len(found) != len(interest_ids):
            raise http_error_invalid_interest_ids()

    await db.execute(delete(CoreUserInterest).where(CoreUserInterest.user_id == user_id))
    for iid in interest_ids:
        db.add(CoreUserInterest(user_id=user_id, interest_id=iid))
    await db.flush()