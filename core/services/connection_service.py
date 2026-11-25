"""Service connessioni 1° grado tra utenti."""

from __future__ import annotations

import logging
import uuid
from datetime import UTC, datetime

from sqlalchemy import and_, or_, select
from sqlalchemy.orm import Session

from auth.models.user import AuthUser
from auth.utils.registration import is_registration_complete
from config import UserStatus
from config.constants import ConnectionStatus, NotificationType
from core.models.connection import CoreProfileConnection
from core.models.profile import CoreProfile
from core.schemas.connection import ConnectionPeerResponse, ConnectionResponse
from core.schemas.public_profile import ViewerConnectionContext
from core.schemas.user_connections import ProfileConnectionPeerResponse
from core.errors.connection_errors import (
    AlreadyConnectedError,
    CannotConnectToSelfError,
    ConnectionAlreadyPendingError,
    ConnectionBlockedError,
    ConnectionNotFoundError,
    InvalidConnectionActionError,
    TargetUserNotFoundError,
)
from core.utils.connections import get_connection_between, ordered_profile_connection_pair
from core.utils.roles import load_connector_user_ids
from notifications.services import connection_payload, notify, snapshot_actor

logger = logging.getLogger(__name__)


def request_connection(
    db: Session,
    viewer: AuthUser,
    target_user_id: uuid.UUID,
) -> ConnectionResponse:
    """Crea richiesta ``pending`` o accetta se esiste già richiesta reciproca."""
    if viewer.id == target_user_id:
        raise CannotConnectToSelfError

    target = _load_connectable_user(db, target_user_id)
    now = _utcnow()
    existing = get_connection_between(db, viewer.id, target.id)

    if existing is not None:
        if existing.status == ConnectionStatus.ACCEPTED:
            raise AlreadyConnectedError
        if existing.status == ConnectionStatus.BLOCKED:
            raise ConnectionBlockedError
        if existing.status == ConnectionStatus.PENDING:
            if existing.initiated_by_id == target.id:
                existing.status = ConnectionStatus.ACCEPTED
                existing.updated_at = now
                _notify_connection(
                    db,
                    recipient_id=target.id,
                    actor_id=viewer.id,
                    connection_id=existing.id,
                    ntype=NotificationType.CONNECTION_ACCEPTED,
                    deep_link="/network?scope=connections",
                )
                db.commit()
                db.refresh(existing)
                logger.info(
                    "connection.auto_accepted connection_id=%s viewer_id=%s target_id=%s",
                    existing.id,
                    viewer.id,
                    target.id,
                )
                return _connection_to_response(db, existing, viewer.id)
            raise ConnectionAlreadyPendingError

    user_low_id, user_high_id = ordered_profile_connection_pair(viewer.id, target.id)
    connection = CoreProfileConnection(
        user_low_id=user_low_id,
        user_high_id=user_high_id,
        status=ConnectionStatus.PENDING,
        initiated_by_id=viewer.id,
        updated_at=now,
    )
    db.add(connection)
    db.flush()
    _notify_connection(
        db,
        recipient_id=target.id,
        actor_id=viewer.id,
        connection_id=connection.id,
        ntype=NotificationType.CONNECTION_REQUEST,
        deep_link="/network?scope=incoming",
    )
    db.commit()
    db.refresh(connection)
    _send_connection_request_email(db, recipient=target, actor=viewer)
    logger.info(
        "connection.requested connection_id=%s viewer_id=%s target_id=%s",
        connection.id,
        viewer.id,
        target.id,
    )
    return _connection_to_response(db, connection, viewer.id)


def accept_connection(
    db: Session,
    viewer: AuthUser,
    connection_id: uuid.UUID,
) -> ConnectionResponse:
    """Accetta richiesta ``pending`` (solo destinatario, non il richiedente)."""
    connection = _get_connection_for_viewer(db, viewer.id, connection_id)
    if connection.status != ConnectionStatus.PENDING:
        raise InvalidConnectionActionError("Only pending connections can be accepted")
    if connection.initiated_by_id == viewer.id:
        raise InvalidConnectionActionError("You cannot accept your own connection request")

    connection.status = ConnectionStatus.ACCEPTED
    connection.updated_at = _utcnow()
    _notify_connection(
        db,
        recipient_id=connection.initiated_by_id,
        actor_id=viewer.id,
        connection_id=connection.id,
        ntype=NotificationType.CONNECTION_ACCEPTED,
        deep_link="/network?scope=connections",
    )
    from admin.services.audit_log import record_audit
    from config.constants import AuditModule

    record_audit(
        db,
        module=AuditModule.NETWORK,
        action="connection.accepted",
        message="Connessione accettata",
        actor=viewer,
        target_type="connection",
        target_id=connection.id,
    )
    db.commit()
    db.refresh(connection)
    logger.info("connection.accepted connection_id=%s user_id=%s", connection.id, viewer.id)
    return _connection_to_response(db, connection, viewer.id)


def decline_connection(
    db: Session,
    viewer: AuthUser,
    connection_id: uuid.UUID,
) -> None:
    """Rifiuta o annulla richiesta ``pending`` (entrambi i partecipanti)."""
    connection = _get_connection_for_viewer(db, viewer.id, connection_id)
    if connection.status != ConnectionStatus.PENDING:
        raise InvalidConnectionActionError("Only pending connections can be declined")

    db.delete(connection)
    from admin.services.audit_log import record_audit
    from config.constants import AuditModule

    record_audit(
        db,
        module=AuditModule.NETWORK,
        action="connection.declined",
        message="Richiesta di connessione rifiutata",
        actor=viewer,
        target_type="connection",
        target_id=connection_id,
    )
    db.commit()
    logger.info("connection.declined connection_id=%s user_id=%s", connection_id, viewer.id)


def list_connections(
    db: Session,
    viewer: AuthUser,
    *,
    status: ConnectionStatus | None = None,
) -> list[ConnectionResponse]:
    """Connessioni dell'utente autenticato, opzionalmente filtrate per stato."""
    query = select(CoreProfileConnection).where(
        or_(
            CoreProfileConnection.user_low_id == viewer.id,
            CoreProfileConnection.user_high_id == viewer.id,
        ),
    )
    if status is not None:
        query = query.where(CoreProfileConnection.status == status)
    query = query.order_by(CoreProfileConnection.updated_at.desc())
    rows = list(db.scalars(query).all())
    connector_ids = load_connector_user_ids(db, [_peer_user_id(row, viewer.id) for row in rows])
    return [
        _connection_to_response(
            db,
            row,
            viewer.id,
            is_connector=_peer_user_id(row, viewer.id) in connector_ids,
        )
        for row in rows
    ]


def list_profile_connections(
    db: Session,
    viewer: AuthUser,
    subject: AuthUser,
) -> list[ProfileConnectionPeerResponse]:
    """Connessioni ``accepted`` del subject, con relazione viewer↔peer."""
    rows = list(
        db.scalars(
            select(CoreProfileConnection)
            .where(
                or_(
                    CoreProfileConnection.user_low_id == subject.id,
                    CoreProfileConnection.user_high_id == subject.id,
                ),
                CoreProfileConnection.status == ConnectionStatus.ACCEPTED,
            )
            .order_by(CoreProfileConnection.updated_at.desc())
        ).all()
    )
    peer_ids = [
        row.user_high_id if row.user_low_id == subject.id else row.user_low_id
        for row in rows
    ]
    if not peer_ids:
        return []

    users_by_id = {
        user.id: user
        for user in db.scalars(select(AuthUser).where(AuthUser.id.in_(peer_ids))).all()
    }
    profiles_by_id = {
        profile.user_id: profile
        for profile in db.scalars(select(CoreProfile).where(CoreProfile.user_id.in_(peer_ids))).all()
    }
    other_ids = [peer_id for peer_id in peer_ids if peer_id != viewer.id]
    viewer_links: dict[uuid.UUID, CoreProfileConnection] = {}
    if other_ids:
        for link in db.scalars(
            select(CoreProfileConnection).where(
                or_(
                    and_(
                        CoreProfileConnection.user_low_id == viewer.id,
                        CoreProfileConnection.user_high_id.in_(other_ids),
                    ),
                    and_(
                        CoreProfileConnection.user_high_id == viewer.id,
                        CoreProfileConnection.user_low_id.in_(other_ids),
                    ),
                )
            )
        ).all():
            other_id = link.user_high_id if link.user_low_id == viewer.id else link.user_low_id
            viewer_links[other_id] = link

    items: list[ProfileConnectionPeerResponse] = []
    connector_ids = load_connector_user_ids(db, peer_ids)
    for peer_id in peer_ids:
        user = users_by_id.get(peer_id)
        if user is None or user.status != UserStatus.ACTIVE:
            continue
        link = viewer_links.get(peer_id)
        if link is not None and link.status == ConnectionStatus.BLOCKED:
            continue
        profile = profiles_by_id.get(peer_id)
        is_self = peer_id == viewer.id
        connection = None
        if not is_self and link is not None:
            connection = ViewerConnectionContext(
                connection_id=link.id,
                status=link.status,
                initiated_by_viewer=link.initiated_by_id == viewer.id,
            )
        items.append(
            ProfileConnectionPeerResponse(
                id=user.id,
                username=str(user.username),
                first_name=str(profile.first_name) if profile is not None and profile.first_name else None,
                last_name=str(profile.last_name) if profile is not None and profile.last_name else None,
                avatar_url=profile.avatar_url if profile is not None else None,
                is_self=is_self,
                connection=connection,
                is_connector=peer_id in connector_ids,
            )
        )
    return items


def _load_connectable_user(db: Session, user_id: uuid.UUID) -> AuthUser:
    """Utente target attivo con onboarding completato."""
    user = db.get(AuthUser, user_id)
    if user is None:
        raise TargetUserNotFoundError
    if user.status != UserStatus.ACTIVE:
        raise TargetUserNotFoundError
    if not is_registration_complete(db, user.id):
        raise TargetUserNotFoundError
    return user


def _get_connection_for_viewer(
    db: Session,
    viewer_id: uuid.UUID,
    connection_id: uuid.UUID,
) -> CoreProfileConnection:
    """Carica connessione se il viewer ne fa parte."""
    connection = db.get(CoreProfileConnection, connection_id)
    if connection is None:
        raise ConnectionNotFoundError
    if viewer_id not in (connection.user_low_id, connection.user_high_id):
        raise ConnectionNotFoundError
    return connection


def _peer_user_id(connection: CoreProfileConnection, viewer_id: uuid.UUID) -> uuid.UUID:
    """Id dell'altro utente nella coppia."""
    if connection.user_low_id == viewer_id:
        return connection.user_high_id
    return connection.user_low_id


def _connection_to_response(
    db: Session,
    connection: CoreProfileConnection,
    viewer_id: uuid.UUID,
    *,
    is_connector: bool | None = None,
) -> ConnectionResponse:
    """Serializza connessione con dati peer."""
    peer_id = _peer_user_id(connection, viewer_id)
    peer_user = db.get(AuthUser, peer_id)
    peer_profile = db.get(CoreProfile, peer_id)
    if peer_user is None:
        raise ConnectionNotFoundError
    connector = (
        is_connector
        if is_connector is not None
        else peer_id in load_connector_user_ids(db, [peer_id])
    )

    return ConnectionResponse(
        id=connection.id,
        status=connection.status,
        initiated_by_me=connection.initiated_by_id == viewer_id,
        peer=ConnectionPeerResponse(
            id=peer_user.id,
            username=str(peer_user.username),
            first_name=str(peer_profile.first_name) if peer_profile is not None else None,
            last_name=str(peer_profile.last_name) if peer_profile is not None else None,
            avatar_url=peer_profile.avatar_url if peer_profile is not None else None,
            is_connector=connector,
        ),
        created_at=connection.created_at,
        updated_at=connection.updated_at,
    )


def _utcnow() -> datetime:
    """Timestamp timezone-aware UTC."""
    return datetime.now(UTC)


def _notify_connection(
    db: Session,
    *,
    recipient_id: uuid.UUID,
    actor_id: uuid.UUID,
    connection_id: uuid.UUID,
    ntype: NotificationType,
    deep_link: str,
) -> None:
    """Scrive inbox nella stessa transazione del cambio connessione."""
    notify(
        db,
        user_id=recipient_id,
        notification_type=ntype,
        payload=connection_payload(
            connection_id=connection_id,
            actor=snapshot_actor(db, actor_id),
            deep_link=deep_link,
        ),
        dedup_key=f"{ntype.value}:{connection_id}",
    )


def _person_names(db: Session, user_id: uuid.UUID) -> tuple[str, str]:
    """Nome completo e nome proprio, vuoti se il profilo non li ha."""
    profile = db.get(CoreProfile, user_id)
    first_name = str(profile.first_name or "").strip() if profile is not None else ""
    last_name = str(profile.last_name or "").strip() if profile is not None else ""
    full_name = " ".join(part for part in (first_name, last_name) if part)
    return full_name, first_name


def _send_connection_request_email(db: Session, *, recipient: AuthUser, actor: AuthUser) -> None:
    """Email transazionale dopo il commit della richiesta. Un errore Brevo non annulla la richiesta."""
    from services.brevo import get_brevo_service

    if not recipient.email:
        return
    try:
        _, recipient_first_name = _person_names(db, recipient.id)
        actor_name, actor_first_name = _person_names(db, actor.id)
        if not actor_name:
            actor_name = str(actor.username or "").strip()
        get_brevo_service().send_connection_request_email(
            email=str(recipient.email),
            first_name=recipient_first_name or "there",
            actor_name=actor_name,
            actor_first_name=actor_first_name,
        )
    except Exception:
        logger.exception(
            "connection.request_email_failed recipient_id=%s actor_id=%s",
            recipient.id,
            actor.id,
        )
