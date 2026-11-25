"""Connessioni in console admin."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from admin.errors import AdminConnectionNotFoundError, AdminUserNotFoundError
from admin.schemas.connections import (
    AdminConnectionItem,
    AdminConnectionListResponse,
    AdminPeerIdentity,
)
from auth.models.user import AuthUser
from config.constants import ConnectionStatus, UserStatus
from core.models.connection import CoreProfileConnection
from core.models.profile import CoreProfile
from core.utils.connections import get_connection_between, ordered_profile_connection_pair
from core.utils.roles import load_user_roles


def list_admin_connections(
    db: Session,
    *,
    status: ConnectionStatus | None,
    user_id: uuid.UUID | None,
    limit: int,
    offset: int,
) -> AdminConnectionListResponse:
    """Elenco globale connessioni 1° grado."""
    query = select(CoreProfileConnection)
    if status is not None:
        query = query.where(CoreProfileConnection.status == status)
    if user_id is not None:
        query = query.where(
            (CoreProfileConnection.user_low_id == user_id)
            | (CoreProfileConnection.user_high_id == user_id)
        )
    total = int(db.scalar(select(func.count()).select_from(query.order_by(None).subquery())) or 0)
    rows = list(
        db.scalars(
            query.order_by(CoreProfileConnection.updated_at.desc()).limit(limit).offset(offset)
        ).all()
    )
    identities = _load_peer_identities(
        db,
        [uid for row in rows for uid in (row.user_low_id, row.user_high_id)],
    )
    items = [_to_item(row, identities) for row in rows]
    return AdminConnectionListResponse(items=items, total=total, limit=limit, offset=offset)


def get_admin_connection(db: Session, connection_id: uuid.UUID) -> AdminConnectionItem:
    """Dettaglio connessione."""
    row = db.get(CoreProfileConnection, connection_id)
    if row is None:
        raise AdminConnectionNotFoundError
    identities = _load_peer_identities(db, [row.user_low_id, row.user_high_id])
    return _to_item(row, identities)


def upsert_admin_connection(
    db: Session,
    *,
    user_a_id: uuid.UUID,
    user_b_id: uuid.UUID,
    status: ConnectionStatus,
    initiated_by_id: uuid.UUID,
) -> AdminConnectionItem:
    """Crea o aggiorna la relazione tra due utenti attivi."""
    _require_active_user(db, user_a_id)
    _require_active_user(db, user_b_id)
    existing = get_connection_between(db, user_a_id, user_b_id)
    now = datetime.now(tz=UTC)
    if existing is None:
        low, high = ordered_profile_connection_pair(user_a_id, user_b_id)
        initiator = initiated_by_id if initiated_by_id in {low, high} else user_a_id
        existing = CoreProfileConnection(
            user_low_id=low,
            user_high_id=high,
            status=status,
            initiated_by_id=initiator,
            created_at=now,
            updated_at=now,
        )
        db.add(existing)
    else:
        existing.status = status
        existing.updated_at = now
        db.add(existing)
    db.commit()
    db.refresh(existing)
    return get_admin_connection(db, existing.id)


def update_admin_connection(
    db: Session,
    connection_id: uuid.UUID,
    status: ConnectionStatus,
) -> AdminConnectionItem:
    """Cambia stato di una connessione esistente."""
    row = db.get(CoreProfileConnection, connection_id)
    if row is None:
        raise AdminConnectionNotFoundError
    row.status = status
    row.updated_at = datetime.now(tz=UTC)
    db.add(row)
    db.commit()
    db.refresh(row)
    return get_admin_connection(db, row.id)


def delete_admin_connection(db: Session, connection_id: uuid.UUID) -> None:
    """Elimina la riga connessione."""
    row = db.get(CoreProfileConnection, connection_id)
    if row is None:
        raise AdminConnectionNotFoundError
    db.delete(row)
    db.commit()


def _require_active_user(db: Session, user_id: uuid.UUID) -> AuthUser:
    user = db.get(AuthUser, user_id)
    if user is None or user.status != UserStatus.ACTIVE:
        raise AdminUserNotFoundError
    return user


def _load_peer_identities(db: Session, user_ids: list[uuid.UUID]) -> dict[uuid.UUID, AdminPeerIdentity]:
    unique_ids = list(dict.fromkeys(user_ids))
    if not unique_ids:
        return {}
    users = {row.id: row for row in db.scalars(select(AuthUser).where(AuthUser.id.in_(unique_ids))).all()}
    profiles = {
        row.user_id: row
        for row in db.scalars(select(CoreProfile).where(CoreProfile.user_id.in_(unique_ids))).all()
    }
    return {
        user_id: AdminPeerIdentity(
            id=user_id,
            username=str(users[user_id].username) if user_id in users else str(user_id),
            first_name=profiles[user_id].first_name if user_id in profiles else None,
            last_name=profiles[user_id].last_name if user_id in profiles else None,
            avatar_url=profiles[user_id].avatar_url if user_id in profiles else None,
            roles=load_user_roles(db, user_id) if user_id in users else [],
        )
        for user_id in unique_ids
    }


def _to_item(
    row: CoreProfileConnection,
    identities: dict[uuid.UUID, AdminPeerIdentity],
) -> AdminConnectionItem:
    return AdminConnectionItem(
        id=row.id,
        status=row.status,
        initiated_by_id=row.initiated_by_id,
        created_at=row.created_at,
        updated_at=row.updated_at,
        user_low=identities[row.user_low_id],
        user_high=identities[row.user_high_id],
    )
