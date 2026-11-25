"""Connessioni console admin."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Path, Query, status
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from admin.errors import AdminServiceError, http_error_admin_internal, http_error_from_admin
from admin.schemas.connections import (
    AdminConnectionItem,
    AdminConnectionListResponse,
    CreateAdminConnectionRequest,
    UpdateAdminConnectionRequest,
)
from admin.services.connection_admin_service import (
    delete_admin_connection,
    get_admin_connection,
    list_admin_connections,
    update_admin_connection,
    upsert_admin_connection,
)
from config.constants import ConnectionStatus
from config.db.session import get_db
from core.dependencies import AdminReadUser, AdminWriteUser

router = APIRouter()


@router.get("", response_model=AdminConnectionListResponse, summary="Elenco connessioni")
def get_admin_connections(
    _user: AdminReadUser,
    db: Session = Depends(get_db),
    status_filter: ConnectionStatus | None = Query(default=None, alias="status"),
    user_id: uuid.UUID | None = Query(default=None),
    limit: int = Query(default=30, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> AdminConnectionListResponse:
    """Lista globale connessioni. Lettura: admin e super_admin."""
    try:
        return list_admin_connections(
            db,
            status=status_filter,
            user_id=user_id,
            limit=limit,
            offset=offset,
        )
    except SQLAlchemyError as exc:
        raise http_error_admin_internal("Unable to list connections") from exc


@router.get("/{connection_id}", response_model=AdminConnectionItem, summary="Dettaglio connessione")
def get_admin_connection_detail(
    _user: AdminReadUser,
    db: Session = Depends(get_db),
    connection_id: uuid.UUID = Path(),
) -> AdminConnectionItem:
    """Dettaglio relazione. Lettura: admin e super_admin."""
    try:
        return get_admin_connection(db, connection_id)
    except AdminServiceError as exc:
        raise http_error_from_admin(exc) from exc
    except SQLAlchemyError as exc:
        raise http_error_admin_internal("Unable to load connection") from exc


@router.post(
    "",
    response_model=AdminConnectionItem,
    status_code=status.HTTP_201_CREATED,
    summary="Crea o aggiorna connessione",
)
def post_admin_connection(
    body: CreateAdminConnectionRequest,
    actor: AdminWriteUser,
    db: Session = Depends(get_db),
) -> AdminConnectionItem:
    """Crea relazione tra due utenti. Scrittura: solo super_admin."""
    try:
        return upsert_admin_connection(
            db,
            user_a_id=body.user_a_id,
            user_b_id=body.user_b_id,
            status=body.status,
            initiated_by_id=actor.id if actor.id in {body.user_a_id, body.user_b_id} else body.user_a_id,
        )
    except AdminServiceError as exc:
        raise http_error_from_admin(exc) from exc
    except SQLAlchemyError as exc:
        raise http_error_admin_internal("Unable to create connection") from exc


@router.patch("/{connection_id}", response_model=AdminConnectionItem, summary="Aggiorna connessione")
def patch_admin_connection(
    body: UpdateAdminConnectionRequest,
    _actor: AdminWriteUser,
    db: Session = Depends(get_db),
    connection_id: uuid.UUID = Path(),
) -> AdminConnectionItem:
    """Cambia stato. Scrittura: solo super_admin."""
    try:
        return update_admin_connection(db, connection_id, body.status)
    except AdminServiceError as exc:
        raise http_error_from_admin(exc) from exc
    except SQLAlchemyError as exc:
        raise http_error_admin_internal("Unable to update connection") from exc


@router.delete("/{connection_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Elimina connessione")
def delete_admin_connection_route(
    _actor: AdminWriteUser,
    db: Session = Depends(get_db),
    connection_id: uuid.UUID = Path(),
) -> None:
    """Rimuove la relazione. Scrittura: solo super_admin."""
    try:
        delete_admin_connection(db, connection_id)
    except AdminServiceError as exc:
        raise http_error_from_admin(exc) from exc
    except SQLAlchemyError as exc:
        raise http_error_admin_internal("Unable to delete connection") from exc
