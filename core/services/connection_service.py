"""Service connessioni 1° grado tra utenti."""

from __future__ import annotations

import logging
import uuid
from datetime import UTC, datetime

from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from auth.models.user import AuthUser
from auth.utils.registration import is_registration_complete
from config import UserStatus
from config.constants import ConnectionStatus
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
from core.utils.connections import get_connection_between

logger = logging.getLogger(__name__)


async def request_connection(
    db: AsyncSession,
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
                await db.commit()
                db.refresh(existing)
                logger.info(
                    "connection.auto_accepted connection_id=%s viewer_id=%s target_id=%s",
                    existing.id,
                    viewer.id,
                    target.id,
                )
                return _connection_to_response(db, existing, viewer.id)
            raise ConnectionAlreadyPendingError

    user_low_id, user_high_id = CoreProfileConnection.ordered_user_pair(viewer.id, target.id)
    connection = CoreProfileConnection(
        user_low_id=user_low_id,
        user_high_id=user_high_id,
        status=ConnectionStatus.PENDING,
        initiated_by_id=viewer.id,
        updated_at=now,
    )
    db.add(connection)
    await db.flush()
    await db.commit()
    db.refresh(connection)
    _send_connection_request_email(db, recipient=target, actor=viewer)
    logger.info(
        "connection.requested connection_id=%s viewer_id=%s target_id=%s",
        connection.id,
        viewer.id,
        target.id,
    )
    return _connection_to_response(db, connection, viewer.id)


async def accept_connection(
    db: AsyncSession,
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
    await db.commit()
    db.refresh(connection)
    logger.info("connection.accepted connection_id=%s user_id=%s", connection.id, viewer.id)
    return _connection_to_response(db, connection, viewer.id)


async def decline_connection(
    db: AsyncSession,
    viewer: AuthUser,
    connection_id: uuid.UUID,
) -> None:
    """Rifiuta o annulla richiesta ``pending`` (entrambi i partecipanti)."""
    connection = _get_connection_for_viewer(db, viewer.id, connection_id)
    if connection.status != ConnectionStatus.PENDING:
        raise InvalidConnectionActionError("Only pending connections can be declined")

    await db.delete(connection)
    await db.commit()
    logger.info("connection.declined connection_id=%s user_id=%s", connection_id, viewer.id)


async def list_connections(
    db: AsyncSession,
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
    rows = list((await db.scalars(query)).all())
    return [
        await _connection_to_response(db, row, viewer.id, is_connector=False)
        for row in rows
    ]


async def list_profile_connections(
    db: AsyncSession,
    viewer: AuthUser,
    subject: AuthUser,
) -> list[ProfileConnectionPeerResponse]:
    """Connessioni ``accepted`` del subject, con relazione viewer↔peer."""
    rows = list(
        (await db.scalars(
            select(CoreProfileConnection)
            .where(
                or_(
                    CoreProfileConnection.user_low_id == subject.id,
                    CoreProfileConnection.user_high_id == subject.id,
                ),
                CoreProfileConnection.status == ConnectionStatus.ACCEPTED,
            )
            .order_by(CoreProfileConnection.updated_at.desc())
        )).all()
    )
    peer_ids = [
        row.user_high_id if row.user_low_id == subject.id else row.user_low_id
        for row in rows
    ]
    if not peer_ids:
        return []

    users_by_id = {
        user.id: user
        for user in (await db.scalars(select(AuthUser).where(AuthUser.id.in_(peer_ids)))).all()
    }
    profiles_by_id = {
        profile.user_id: profile
        for profile in (await db.scalars(select(CoreProfile).where(CoreProfile.user_id.in_(peer_ids)))).all()
    }
    other_ids = [peer_id for peer_id in peer_ids if peer_id != viewer.id]
    viewer_links: dict[uuid.UUID, CoreProfileConnection] = {}
    if other_ids:
        for link in (await db.scalars(
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
        )).all():
            other_id = link.user_high_id if link.user_low_id == viewer.id else link.user_low_id
            viewer_links[other_id] = link

    items: list[ProfileConnectionPeerResponse] = []
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
                is_connector=False,
            )
        )
    return items


async def _load_connectable_user(db: AsyncSession, user_id: uuid.UUID) -> AuthUser:
    """Utente target attivo con onboarding completato."""
    user = await db.get(AuthUser, user_id)
    if user is None:
        raise TargetUserNotFoundError
    if user.status != UserStatus.ACTIVE:
        raise TargetUserNotFoundError
    if not await is_registration_complete(db, user.id):
        raise TargetUserNotFoundError
    return user


async def _get_connection_for_viewer(
    db: AsyncSession,
    viewer_id: uuid.UUID,
    connection_id: uuid.UUID,
) -> CoreProfileConnection:
    """Carica connessione se il viewer ne fa parte."""
    connection = await db.get(CoreProfileConnection, connection_id)
    if connection is None:
        raise ConnectionNotFoundError
    if not connection.involves_user(viewer_id):
        raise ConnectionNotFoundError
    return connection


async def _connection_to_response(
    db: AsyncSession,
    connection: CoreProfileConnection,
    viewer_id: uuid.UUID,
    *,
    is_connector: bool | None = None,
) -> ConnectionResponse:
    """Serializza connessione con dati peer."""
    peer_id = connection.peer_user_id(viewer_id)
    peer_user = await db.get(AuthUser, peer_id)
    peer_profile = await db.get(CoreProfile, peer_id)
    if peer_user is None:
        raise ConnectionNotFoundError
    connector = (
        is_connector
        if is_connector is not None
        else False
    )

    return ConnectionResponse(
        id=connection.id,
        status=connection.status,
        initiated_by_me=connection.initiated_by_viewer(viewer_id),
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


async def _person_names(db: AsyncSession, user_id: uuid.UUID) -> tuple[str, str]:
    """Nome completo e nome proprio, vuoti se il profilo non li ha."""
    profile = await db.get(CoreProfile, user_id)
    if profile is None:
        return "", ""
    return profile.full_name, profile.given_name


def _send_connection_request_email(db: AsyncSession, *, recipient: AuthUser, actor: AuthUser) -> None:
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
