"""Helper connessioni 1° grado tra utenti."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import case, func, or_, select
from sqlalchemy.orm import Session

from config.constants import ConnectionStatus
from core.models.connection import CoreProfileConnection


def ordered_profile_connection_pair(
    user_id_a: uuid.UUID,
    user_id_b: uuid.UUID,
) -> tuple[uuid.UUID, uuid.UUID]:
    """`(user_low_id, user_high_id)` con UUID ordinati per `core_profile_connections`."""
    if user_id_a == user_id_b:
        msg = "core_profile_connections: servono due utenti distinti"
        raise ValueError(msg)
    if user_id_a < user_id_b:
        return user_id_a, user_id_b
    return user_id_b, user_id_a


def get_connection_between(
    db: Session,
    user_id_a: uuid.UUID,
    user_id_b: uuid.UUID,
) -> CoreProfileConnection | None:
    """Riga connessione canonica tra due utenti distinti, se presente."""
    user_low_id, user_high_id = ordered_profile_connection_pair(user_id_a, user_id_b)
    return db.scalar(
        select(CoreProfileConnection).where(
            CoreProfileConnection.user_low_id == user_low_id,
            CoreProfileConnection.user_high_id == user_high_id,
        )
    )


def load_accepted_neighbor_ids(db: Session, user_id: uuid.UUID) -> set[uuid.UUID]:
    """Id utenti con connessione ``accepted`` rispetto a ``user_id``."""
    neighbor_id = case(
        (CoreProfileConnection.user_low_id == user_id, CoreProfileConnection.user_high_id),
        else_=CoreProfileConnection.user_low_id,
    )
    rows = db.scalars(
        select(neighbor_id).where(
            or_(
                CoreProfileConnection.user_low_id == user_id,
                CoreProfileConnection.user_high_id == user_id,
            ),
            CoreProfileConnection.status == ConnectionStatus.ACCEPTED,
        )
    ).all()
    return set(rows)


def _accepted_neighbor_id_subquery(user_id: uuid.UUID):
    """Subquery ``neighbor_id`` delle connessioni ``accepted`` di ``user_id``."""
    neighbor_id = case(
        (CoreProfileConnection.user_low_id == user_id, CoreProfileConnection.user_high_id),
        else_=CoreProfileConnection.user_low_id,
    )
    return (
        select(neighbor_id.label("neighbor_id"))
        .where(
            or_(
                CoreProfileConnection.user_low_id == user_id,
                CoreProfileConnection.user_high_id == user_id,
            ),
            CoreProfileConnection.status == ConnectionStatus.ACCEPTED,
        )
        .subquery(f"accepted_neighbors_{user_id.hex[:12]}")
    )


def count_mutual_accepted_connections(
    db: Session,
    user_id_a: uuid.UUID,
    user_id_b: uuid.UUID,
) -> int:
    """Conteggio connessioni accettate in comune tra due utenti."""
    if user_id_a == user_id_b:
        return 0
    neighbors_a = _accepted_neighbor_id_subquery(user_id_a)
    neighbors_b = _accepted_neighbor_id_subquery(user_id_b)
    count = db.scalar(
        select(func.count())
        .select_from(neighbors_a)
        .join(neighbors_b, neighbors_a.c.neighbor_id == neighbors_b.c.neighbor_id)
    )
    return int(count or 0)


def count_accepted_connections(db: Session, user_id: uuid.UUID) -> int:
    """Conteggio connessioni ``accepted`` dell'utente (1° grado)."""
    pair_filter = or_(
        CoreProfileConnection.user_low_id == user_id,
        CoreProfileConnection.user_high_id == user_id,
    )
    count = db.scalar(
        select(func.count())
        .select_from(CoreProfileConnection)
        .where(pair_filter, CoreProfileConnection.status == ConnectionStatus.ACCEPTED)
    )
    return int(count or 0)


def is_accepted_connection(connection: CoreProfileConnection | None) -> bool:
    """True se esiste una relazione 1° grado ``accepted``."""
    return connection is not None and connection.status == ConnectionStatus.ACCEPTED


def ensure_accepted_connection(
    db: Session,
    user_id_a: uuid.UUID,
    user_id_b: uuid.UUID,
    *,
    initiated_by_id: uuid.UUID,
) -> CoreProfileConnection | None:
    """Crea o promuove a ``accepted`` la connessione tra due utenti.

    Non tocca relazioni ``blocked``. Non invia notifiche (flusso invito signup).
    """
    if user_id_a == user_id_b:
        return None
    existing = get_connection_between(db, user_id_a, user_id_b)
    now = datetime.now(tz=UTC)
    if existing is not None:
        if existing.status == ConnectionStatus.BLOCKED:
            return existing
        if existing.status != ConnectionStatus.ACCEPTED:
            existing.status = ConnectionStatus.ACCEPTED
            existing.updated_at = now
            db.add(existing)
        return existing

    user_low_id, user_high_id = ordered_profile_connection_pair(user_id_a, user_id_b)
    if initiated_by_id not in {user_low_id, user_high_id}:
        initiated_by_id = user_id_a
    connection = CoreProfileConnection(
        user_low_id=user_low_id,
        user_high_id=user_high_id,
        status=ConnectionStatus.ACCEPTED,
        initiated_by_id=initiated_by_id,
        created_at=now,
        updated_at=now,
    )
    db.add(connection)
    return connection

