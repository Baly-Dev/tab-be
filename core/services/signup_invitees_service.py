"""Lista profili iscritti tramite il link invito del viewer."""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from auth.models.user import AuthUser
from auth.utils.invites import count_signup_invites
from config import UserStatus
from core.models.profile import CoreProfile
from core.schemas.invites import SignupInviteeItem, SignupInviteesListResponse
from core.utils.roles import load_connector_user_ids

_DEFAULT_LIMIT = 50
_MAX_LIMIT = 100


def list_signup_invitees(
    db: Session,
    inviter_id: uuid.UUID,
    *,
    limit: int = _DEFAULT_LIMIT,
    offset: int = 0,
) -> SignupInviteesListResponse:
    """Utenti con ``invited_by_id`` = viewer, esclusi gli account eliminati."""
    safe_limit = min(max(limit, 1), _MAX_LIMIT)
    safe_offset = max(offset, 0)
    total = count_signup_invites(db, inviter_id)

    rows = db.execute(
        select(AuthUser, CoreProfile)
        .outerjoin(CoreProfile, CoreProfile.user_id == AuthUser.id)
        .where(
            AuthUser.invited_by_id == inviter_id,
            AuthUser.status != UserStatus.DELETED,
        )
        .order_by(AuthUser.created_at.desc())
        .limit(safe_limit)
        .offset(safe_offset)
    ).all()

    connector_ids = load_connector_user_ids(db, (user.id for user, _profile in rows))
    items = [
        SignupInviteeItem(
            id=user.id,
            username=str(user.username),
            first_name=str(profile.first_name) if profile is not None else None,
            last_name=str(profile.last_name) if profile is not None else None,
            avatar_url=str(profile.avatar_url) if profile is not None and profile.avatar_url else None,
            current_job_position=(
                str(profile.current_job_position)
                if profile is not None and profile.current_job_position
                else None
            ),
            current_company_name=(
                str(profile.current_company_name)
                if profile is not None and profile.current_company_name
                else None
            ),
            is_connector=user.id in connector_ids,
            signed_up_at=user.created_at,
        )
        for user, profile in rows
    ]
    return SignupInviteesListResponse(
        items=items,
        total=total,
        limit=safe_limit,
        offset=safe_offset,
    )
