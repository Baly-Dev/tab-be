"""Service ricerca membri."""

from __future__ import annotations

import re
import uuid

from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from auth.models.user import AuthUser
from config.constants import ConnectionStatus
from core.models.connection import CoreProfileConnection
from core.models.profile import CoreProfile
from core.errors.member_search_errors import InvalidSearchQueryError
from core.schemas.member_search import MemberSearchItem, MemberSearchResponse
from core.services.member_search_policy import (
    MemberSearchContext,
    apply_member_search_visibility,
    assert_member_search_allowed,
)

_MIN_QUERY_LEN = 2
_MAX_QUERY_LEN = 64
_DEFAULT_LIMIT = 20
_MAX_LIMIT = 50

_MULTI_SPACE_RE = re.compile(r"\s+")


def normalize_member_search_query(raw: str) -> str:
    """Normalizza e valida la query utente."""
    normalized = _MULTI_SPACE_RE.sub(" ", raw.strip())
    if len(normalized) < _MIN_QUERY_LEN:
        raise InvalidSearchQueryError(
            f"Search query must be at least {_MIN_QUERY_LEN} characters",
        )
    if len(normalized) > _MAX_QUERY_LEN:
        raise InvalidSearchQueryError(
            f"Search query must be at most {_MAX_QUERY_LEN} characters",
        )
    return normalized


def escape_like_pattern(value: str) -> str:
    """Escape caratteri speciali per ``ILIKE`` PostgreSQL."""
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


async def search_members(
    db: AsyncSession,
    viewer: AuthUser,
    *,
    query: str,
    limit: int = _DEFAULT_LIMIT,
    offset: int = 0,
) -> MemberSearchResponse:
    """Cerca membri per nome, cognome, username o nome completo."""
    context = assert_member_search_allowed(db, viewer)
    normalized = normalize_member_search_query(query)
    safe_limit = min(max(limit, 1), _MAX_LIMIT)
    safe_offset = max(offset, 0)
    pattern = f"%{escape_like_pattern(normalized)}%"

    full_name = func.concat(CoreProfile.first_name, " ", CoreProfile.last_name)
    match_filter = or_(
        CoreProfile.first_name.ilike(pattern, escape="\\"),
        CoreProfile.last_name.ilike(pattern, escape="\\"),
        AuthUser.username.ilike(pattern, escape="\\"),
        full_name.ilike(pattern, escape="\\"),
    )

    base_query = (
        select(AuthUser, CoreProfile)
        .join(CoreProfile, CoreProfile.user_id == AuthUser.id)
        .where(match_filter)
    )
    visible_query = apply_member_search_visibility(base_query, context=context)

    count_query = select(func.count()).select_from(visible_query.subquery())
    total = int(await db.scalar(count_query) or 0)

    rows = await db.execute(
        visible_query.order_by(
            CoreProfile.first_name.asc(),
            CoreProfile.last_name.asc(),
            AuthUser.username.asc(),
        )
        .offset(safe_offset)
        .limit(safe_limit),
    ).all()

    user_ids = [user_row.id for user_row, _ in rows]
    connection_status_by_user = await _load_connection_statuses(db, context.viewer_id, user_ids)

    items = [
        _row_to_search_item(
            user_row,
            profile_row,
            connection_status_by_user.get(user_row.id),
            False,
        )
        for user_row, profile_row in rows
    ]
    return MemberSearchResponse(query=normalized, items=items, total=total)


async def _load_connection_statuses(
    db: AsyncSession,
    viewer_id: uuid.UUID,
    peer_ids: list[uuid.UUID],
) -> dict[uuid.UUID, ConnectionStatus]:
    """Mappa peer_id → status connessione con il viewer (batch)."""
    if not peer_ids:
        return {}
    rows = (await db.scalars(
        select(CoreProfileConnection).where(
            or_(
                and_(
                    CoreProfileConnection.user_low_id == viewer_id,
                    CoreProfileConnection.user_high_id.in_(peer_ids),
                ),
                and_(
                    CoreProfileConnection.user_high_id == viewer_id,
                    CoreProfileConnection.user_low_id.in_(peer_ids),
                ),
            ),
        ),
    )).all()
    statuses: dict[uuid.UUID, ConnectionStatus] = {}
    for row in rows:
        peer_id = row.user_high_id if row.user_low_id == viewer_id else row.user_low_id
        statuses[peer_id] = row.status
    return statuses


def _row_to_search_item(
    user: AuthUser,
    profile: CoreProfile,
    connection_status: ConnectionStatus | None,
    is_connector: bool,
) -> MemberSearchItem:
    """Mappa riga DB → risultato leggero."""
    connected = connection_status == ConnectionStatus.ACCEPTED
    return MemberSearchItem(
        id=user.id,
        username=str(user.username),
        first_name=str(profile.first_name),
        last_name=str(profile.last_name),
        avatar_url=profile.avatar_url,
        current_job_position=profile.current_job_position,
        residence_city=profile.residence_city if connected else None,
        connection_status=connection_status,
        is_connector=is_connector,
    )
