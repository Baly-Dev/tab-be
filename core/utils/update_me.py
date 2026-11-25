"""Aggiornamento profilo proprio (PATCH /core/me)."""

from __future__ import annotations

import uuid

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

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
from notifications.services.profile_incomplete import sync_profile_incomplete_notification

_PROFILE_PATCH_FIELDS = (
    "first_name",
    "last_name",
    "birth_date",
    "gender",
    "residence_country",
    "residence_city",
    "bio",
    "avatar_url",
    "current_company_name",
    "current_job_position",
    "linkedin_url",
)

_COMPLETENESS_FIELDS = (
    "first_name",
    "last_name",
    "bio",
    "avatar_url",
    "residence_country",
    "residence_city",
    "current_company_name",
    "current_job_position",
    "linkedin_url",
    "birth_date",
)


def update_me(db: Session, user: AuthUser, body: UpdateMeRequest) -> MeResponse:
    """Applica patch al profilo (e interessi se presenti) e restituisce ``MeResponse``."""
    payload = body.model_dump(exclude_unset=True)
    if not payload:
        raise http_error_empty_update()

    profile = db.get(CoreProfile, user.id)
    if profile is None:
        raise http_error_for_own_profile_missing()

    interest_ids: list[uuid.UUID] | None = payload.pop("interest_ids", None)

    for key in _PROFILE_PATCH_FIELDS:
        if key not in payload:
            continue
        setattr(profile, key, payload[key])

    if interest_ids is not None:
        _replace_interests(db, user.id, interest_ids)

    has_interests = (
        db.scalar(
            select(CoreUserInterest.interest_id).where(CoreUserInterest.user_id == user.id).limit(1)
        )
        is not None
    )
    refresh_profile_completeness(profile, has_interests)
    db.add(profile)
    sync_profile_incomplete_notification(db, user)
    db.commit()

    return build_me_response(db, user)


def _replace_interests(db: Session, user_id: uuid.UUID, interest_ids: list[uuid.UUID]) -> None:
    """Valida e sostituisce gli interessi dell'utente (lista vuota = nessuno)."""
    if interest_ids:
        found = db.scalars(
            select(CoreInterest.id).where(
                CoreInterest.id.in_(interest_ids),
                CoreInterest.is_active.is_(True),
            )
        ).all()
        if len(found) != len(interest_ids):
            raise http_error_invalid_interest_ids()

    db.execute(delete(CoreUserInterest).where(CoreUserInterest.user_id == user_id))
    for iid in interest_ids:
        db.add(CoreUserInterest(user_id=user_id, interest_id=iid))
    db.flush()


def _compute_profile_completeness(profile: CoreProfile, has_interests: bool) -> int:
    """Stima 0–100 in base ai campi profilo compilati (+ interessi)."""
    filled = sum(1 for field in _COMPLETENESS_FIELDS if _is_filled(getattr(profile, field, None)))
    if has_interests:
        filled += 1
    total = len(_COMPLETENESS_FIELDS) + 1
    return int(round(100 * filled / total))


def refresh_profile_completeness(profile: CoreProfile, has_interests: bool) -> None:
    """Ricalcola ``profile_completeness`` sul modello (senza commit)."""
    profile.profile_completeness = _compute_profile_completeness(profile, has_interests)


def _is_filled(value: object) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    return True
