"""API inbox notifiche (utente autenticato)."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Path, Query, status
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from auth.utils.helpers import AuthenticatedUser
from config.db.session import get_db
from notifications.errors import NotificationServiceError, http_error_from_notification
from notifications.schemas.notification import (
    MarkAllReadResponse,
    NotificationListResponse,
    NotificationResponse,
    UnreadCountResponse,
)
from notifications.services.inbox import (
    count_unread,
    delete_notification,
    list_notifications,
    mark_all_read,
    mark_read,
    to_response,
)

router = APIRouter()


@router.get(
    "/",
    response_model=NotificationListResponse,
    summary="Lista notifiche dell'utente autenticato",
)
def get_notifications(
    user: AuthenticatedUser,
    db: Session = Depends(get_db),
    limit: int = Query(default=20, ge=1, le=50),
    offset: int = Query(default=0, ge=0),
    unread_only: bool = Query(default=False),
) -> NotificationListResponse:
    """Inbox paginata, più recenti prima."""
    try:
        rows, total, unread = list_notifications(
            db,
            user.id,
            limit=limit,
            offset=offset,
            unread_only=unread_only,
        )
    except SQLAlchemyError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"code": "internal_error", "message": "Unable to load notifications"},
        ) from exc
    return NotificationListResponse(
        items=[to_response(row) for row in rows],
        total=total,
        unread_count=unread,
        limit=limit,
        offset=offset,
    )


@router.get(
    "/unread-count",
    response_model=UnreadCountResponse,
    summary="Conteggio notifiche non lette (badge)",
)
def get_unread_count(
    user: AuthenticatedUser,
    db: Session = Depends(get_db),
) -> UnreadCountResponse:
    """Usato dal client in polling. Stesso dato incluso in GET lista."""
    try:
        return UnreadCountResponse(unread_count=count_unread(db, user.id))
    except SQLAlchemyError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"code": "internal_error", "message": "Unable to load unread count"},
        ) from exc


@router.patch(
    "/read-all",
    response_model=MarkAllReadResponse,
    summary="Segna tutte le notifiche come lette",
)
def patch_read_all(
    user: AuthenticatedUser,
    db: Session = Depends(get_db),
) -> MarkAllReadResponse:
    """Azione massiva sull'inbox del destinatario."""
    try:
        updated = mark_all_read(db, user.id)
    except SQLAlchemyError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"code": "internal_error", "message": "Unable to mark notifications as read"},
        ) from exc
    return MarkAllReadResponse(updated=updated)


@router.patch(
    "/{notification_id}/read",
    response_model=NotificationResponse,
    summary="Segna una notifica come letta",
)
def patch_read_one(
    user: AuthenticatedUser,
    db: Session = Depends(get_db),
    notification_id: uuid.UUID = Path(description="UUID notifica."),
) -> NotificationResponse:
    """Idempotente se già letta. 404 se non appartiene all'utente."""
    try:
        row = mark_read(db, user.id, notification_id)
    except NotificationServiceError as exc:
        raise http_error_from_notification(exc) from exc
    except SQLAlchemyError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"code": "internal_error", "message": "Unable to mark notification as read"},
        ) from exc
    return to_response(row)


@router.delete(
    "/{notification_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Elimina una notifica",
)
def delete_one(
    user: AuthenticatedUser,
    db: Session = Depends(get_db),
    notification_id: uuid.UUID = Path(description="UUID notifica."),
) -> None:
    """Rimuove la riga inbox del destinatario. 404 se non appartiene all'utente."""
    try:
        delete_notification(db, user.id, notification_id)
    except NotificationServiceError as exc:
        raise http_error_from_notification(exc) from exc
    except SQLAlchemyError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"code": "internal_error", "message": "Unable to delete notification"},
        ) from exc
