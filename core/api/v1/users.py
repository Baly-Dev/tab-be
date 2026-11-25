"""Profilo pubblico utente per handle ``username``."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Path
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from auth.models.user import AuthUser
from auth.utils.helpers import AuthenticatedUser
from config import UserStatus
from config.constants import ConnectionStatus
from config.db.session import get_db
from core.errors import (
    http_error_for_profile_connections_forbidden,
    http_error_for_profile_not_found,
)
from core.models.interest import CoreInterest
from core.models.profile import CoreProfile
from core.models.user_interest import CoreUserInterest
from core.schemas.public_profile import (
    PublicProfileInterestItem,
    PublicProfileResponse,
    ViewerConnectionContext,
)
from core.schemas.user_connections import ProfileConnectionsListResponse
from core.services.connection_service import list_profile_connections
from core.utils.connections import (
    count_accepted_connections,
    count_mutual_accepted_connections,
    get_connection_between,
)
from core.utils.profile_stats import count_user_posts
from core.utils.profile_visibility import can_view_full_profile
from core.utils.roles import load_user_roles, public_identity_roles

router = APIRouter()


@router.get(
    "/{username}",
    response_model=PublicProfileResponse,
    summary="Profilo pubblico utente",
)
def get_public_profile(
    user: AuthenticatedUser,
    db: Session = Depends(get_db),
    username: str = Path(
        min_length=3,
        max_length=32,
        pattern=r"^[a-z0-9_]+$",
        description="Handle pubblico (case-insensitive).",
    ),
) -> PublicProfileResponse:
    """Profilo visibile a chi è in rete (accepted). Senza connessione: identità e ruolo."""
    normalized = username.strip().lower()
    if not normalized:
        raise http_error_for_profile_not_found()

    subject_row = db.execute(
        select(AuthUser, CoreProfile)
        .join(CoreProfile, CoreProfile.user_id == AuthUser.id)
        .where(
            AuthUser.username == normalized,
            AuthUser.status == UserStatus.ACTIVE,
        )
    ).first()
    if subject_row is None:
        raise http_error_for_profile_not_found()
    subject, profile_row = subject_row

    is_self = subject.id == user.id
    connection_row = None if is_self else get_connection_between(db, user.id, subject.id)
    if connection_row is not None and connection_row.status == ConnectionStatus.BLOCKED:
        raise http_error_for_profile_not_found()

    connection_context = None
    if not is_self and connection_row is not None:
        connection_context = ViewerConnectionContext(
            connection_id=connection_row.id,
            status=connection_row.status,
            initiated_by_viewer=connection_row.initiated_by_id == user.id,
        )

    profile_visible = can_view_full_profile(
        viewer_id=user.id,
        subject_id=subject.id,
        connection=connection_row,
    )
    if not profile_visible:
        return PublicProfileResponse(
            id=subject.id,
            username=str(subject.username),
            is_self=is_self,
            roles=public_identity_roles(load_user_roles(db, subject.id)),
            interests=[],
            first_name=str(profile_row.first_name),
            last_name=str(profile_row.last_name),
            bio=None,
            avatar_url=profile_row.avatar_url,
            current_job_position=profile_row.current_job_position,
            current_company_name=profile_row.current_company_name,
            profile_visible=False,
            connection=connection_context,
            joined_at=subject.created_at,
        )

    interest_rows = db.execute(
        select(CoreInterest.id, CoreInterest.name)
        .join(CoreUserInterest, CoreUserInterest.interest_id == CoreInterest.id)
        .where(CoreUserInterest.user_id == subject.id)
        .order_by(CoreInterest.sort_order, CoreInterest.name)
    ).all()
    interests = [
        PublicProfileInterestItem(id=row.id, name=str(row.name)) for row in interest_rows
    ]

    mutual_count = 0 if is_self else count_mutual_accepted_connections(db, user.id, subject.id)

    return PublicProfileResponse(
        id=subject.id,
        username=str(subject.username),
        is_self=is_self,
        roles=load_user_roles(db, subject.id),
        interests=interests,
        first_name=str(profile_row.first_name),
        last_name=str(profile_row.last_name),
        bio=profile_row.bio,
        avatar_url=profile_row.avatar_url,
        current_company_name=profile_row.current_company_name,
        current_job_position=profile_row.current_job_position,
        residence_country=profile_row.residence_country,
        residence_city=profile_row.residence_city,
        profile_completeness=int(profile_row.profile_completeness or 0),
        connection=connection_context,
        mutual_connections_count=mutual_count,
        connections_count=count_accepted_connections(db, subject.id),
        post_counts=count_user_posts(db, subject.id),
        profile_visible=True,
        joined_at=subject.created_at,
    )


@router.get(
    "/{username}/connections",
    response_model=ProfileConnectionsListResponse,
    summary="Connessioni del profilo pubblico",
)
def get_profile_connections(
    user: AuthenticatedUser,
    db: Session = Depends(get_db),
    username: str = Path(
        min_length=3,
        max_length=32,
        pattern=r"^[a-z0-9_]+$",
        description="Handle pubblico (case-insensitive).",
    ),
) -> ProfileConnectionsListResponse:
    """Elenco connessioni accepted dell'utente. Visibile solo a sé stessi o a chi è connected."""
    normalized = username.strip().lower()
    if not normalized:
        raise http_error_for_profile_not_found()

    subject = db.scalar(
        select(AuthUser).where(
            AuthUser.username == normalized,
            AuthUser.status == UserStatus.ACTIVE,
        )
    )
    if subject is None:
        raise http_error_for_profile_not_found()

    connection_row = None if subject.id == user.id else get_connection_between(db, user.id, subject.id)
    if connection_row is not None and connection_row.status == ConnectionStatus.BLOCKED:
        raise http_error_for_profile_not_found()
    if not can_view_full_profile(
        viewer_id=user.id,
        subject_id=subject.id,
        connection=connection_row,
    ):
        raise http_error_for_profile_connections_forbidden()

    try:
        items = list_profile_connections(db, user, subject)
    except SQLAlchemyError as exc:
        raise _http_error_internal("Unable to load profile connections") from exc
    return ProfileConnectionsListResponse(items=items, total=len(items))


def _http_error_internal(message: str) -> HTTPException:
    """500 generico del profilo pubblico."""
    return HTTPException(
        status_code=500,
        detail={"code": "internal_error", "message": message},
    )
