"""API connessioni 1° grado tra utenti."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Path, Query, status
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from auth.utils.helpers import AuthenticatedUser
from config.constants import ConnectionStatus
from config.db import get_async_db
from core.errors import (
    ConnectionServiceError,
    http_error_from_connection,
)
from core.schemas.connection import (
    ConnectionListResponse,
    ConnectionResponse,
    CreateConnectionRequest,
)
from core.services.connection_service import (
    accept_connection,
    decline_connection,
    list_connections,
    request_connection,
)

router = APIRouter()


@router.post(
    "",
    response_model=ConnectionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Richiedi connessione",
)
async def post_connection_request(
    body: CreateConnectionRequest,
    user: AuthenticatedUser,
    db: AsyncSession = Depends(get_async_db),
) -> ConnectionResponse:
    """Invia richiesta ``pending`` a un altro utente attivo."""
    try:
        return await request_connection(db, user, body.target_user_id)
    except ConnectionServiceError as exc:
        raise http_error_from_connection(exc) from exc
    except SQLAlchemyError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"code": "internal_error", "message": "Unable to create connection request"},
        ) from exc


@router.get(
    "",
    response_model=ConnectionListResponse,
    summary="Lista connessioni",
)
async def get_connections(
    user: AuthenticatedUser,
    db: AsyncSession = Depends(get_async_db),
    status_filter: ConnectionStatus | None = Query(
        default=None,
        alias="status",
        description="Filtra per stato: pending, accepted, blocked.",
    ),
) -> ConnectionListResponse:
    """Connessioni dell'utente autenticato."""
    try:
        items = await list_connections(db, user, status=status_filter)
    except SQLAlchemyError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"code": "internal_error", "message": "Unable to load connections"},
        ) from exc
    return ConnectionListResponse(items=items, total=len(items))


@router.post(
    "/{connection_id}/accept",
    response_model=ConnectionResponse,
    summary="Accetta richiesta connessione",
)
async def post_accept_connection(
    user: AuthenticatedUser,
    db: AsyncSession = Depends(get_async_db),
    connection_id: uuid.UUID = Path(description="UUID connessione."),
) -> ConnectionResponse:
    """Accetta richiesta ``pending`` ricevuta da un altro utente."""
    try:
        return await accept_connection(db, user, connection_id)
    except ConnectionServiceError as exc:
        raise http_error_from_connection(exc) from exc
    except SQLAlchemyError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"code": "internal_error", "message": "Unable to accept connection"},
        ) from exc


@router.post(
    "/{connection_id}/decline",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Rifiuta o annulla richiesta connessione",
)
async def post_decline_connection(
    user: AuthenticatedUser,
    db: AsyncSession = Depends(get_async_db),
    connection_id: uuid.UUID = Path(description="UUID connessione."),
) -> None:
    """Elimina richiesta ``pending`` (destinatario rifiuta o richiedente annulla)."""
    try:
        await decline_connection(db, user, connection_id)
    except ConnectionServiceError as exc:
        raise http_error_from_connection(exc) from exc
    except SQLAlchemyError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"code": "internal_error", "message": "Unable to decline connection"},
        ) from exc