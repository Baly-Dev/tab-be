"""KPI overview console admin."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from admin.schemas.overview import (
    AdminOverviewNetwork,
    AdminOverviewResponse,
    AdminOverviewSeriesPoint,
    AdminOverviewUsers,
)
from auth.models.user import AuthUser
from config.constants import AppRole, ConnectionStatus, UserStatus
from core.models.connection import CoreProfileConnection
from core.models.user_role import CoreUserRole
from core.permissions import Permission, user_has_permission

_SERIES_DAYS = 30


def load_admin_overview(db: Session, viewer: AuthUser) -> AdminOverviewResponse:
    """Aggregati utenti e rete per la dashboard staff."""
    now = datetime.now(tz=UTC)
    since_7 = now - timedelta(days=7)
    since_30 = now - timedelta(days=30)

    status_rows = db.execute(select(AuthUser.status, func.count()).group_by(AuthUser.status)).all()
    by_status = {row[0]: int(row[1]) for row in status_rows}

    users = AdminOverviewUsers(
        total=int(
            db.scalar(
                select(func.count()).select_from(AuthUser).where(AuthUser.status != UserStatus.DELETED)
            )
            or 0
        ),
        active=by_status.get(UserStatus.ACTIVE, 0),
        pending=by_status.get(UserStatus.PENDING, 0),
        suspended=by_status.get(UserStatus.SUSPENDED, 0),
        deleted=0,
        new_7d=int(
            db.scalar(
                select(func.count())
                .select_from(AuthUser)
                .where(AuthUser.created_at >= since_7, AuthUser.status != UserStatus.DELETED)
            )
            or 0
        ),
        new_30d=int(
            db.scalar(
                select(func.count())
                .select_from(AuthUser)
                .where(AuthUser.created_at >= since_30, AuthUser.status != UserStatus.DELETED)
            )
            or 0
        ),
        connectors=int(
            db.scalar(
                select(func.count()).select_from(CoreUserRole).where(CoreUserRole.role == AppRole.CONNECTOR)
            )
            or 0
        ),
        invited=int(
            db.scalar(
                select(func.count())
                .select_from(AuthUser)
                .where(AuthUser.invited_by_id.is_not(None), AuthUser.status != UserStatus.DELETED)
            )
            or 0
        ),
    )

    conn_rows = db.execute(
        select(CoreProfileConnection.status, func.count()).group_by(CoreProfileConnection.status)
    ).all()
    conn_by_status = {row[0]: int(row[1]) for row in conn_rows}
    network = AdminOverviewNetwork(
        accepted=conn_by_status.get(ConnectionStatus.ACCEPTED, 0),
        pending=conn_by_status.get(ConnectionStatus.PENDING, 0),
        blocked=conn_by_status.get(ConnectionStatus.BLOCKED, 0),
    )

    return AdminOverviewResponse(
        can_write=user_has_permission(db, viewer.id, Permission.ADMIN_WRITE),
        users=users,
        network=network,
        signups_30d=_daily_series(db, AuthUser.created_at, now=now),
    )


def _daily_series(db: Session, timestamp_col, *, now: datetime) -> list[AdminOverviewSeriesPoint]:
    start_date = now.astimezone(UTC).date() - timedelta(days=_SERIES_DAYS - 1)
    since = datetime(start_date.year, start_date.month, start_date.day, tzinfo=UTC)
    day_expr = func.date_trunc("day", func.timezone("UTC", timestamp_col))
    rows = db.execute(select(day_expr, func.count()).where(timestamp_col >= since).group_by(day_expr)).all()
    by_day: dict[str, int] = {}
    for raw_day, count in rows:
        if raw_day is None:
            continue
        if isinstance(raw_day, datetime):
            key = raw_day.astimezone(UTC).date().isoformat() if raw_day.tzinfo else raw_day.date().isoformat()
        else:
            key = raw_day.isoformat()
        by_day[key] = int(count)
    return [
        AdminOverviewSeriesPoint(
            date=(start_date + timedelta(days=offset)).isoformat(),
            count=by_day.get((start_date + timedelta(days=offset)).isoformat(), 0),
        )
        for offset in range(_SERIES_DAYS)
    ]
