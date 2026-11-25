"""Utenti console admin."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Path, Query
from fastapi.responses import Response
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from admin.errors import AdminServiceError, http_error_admin_internal, http_error_from_admin
from admin.schemas.users import (
    AdminUserDeletedResponse,
    AdminUserDetail,
    AdminUserListResponse,
    AdminUserSort,
    ExportAdminUsersRequest,
    LinkAdminSignupInviteRequest,
    SortOrder,
    UpdateAdminUserRequest,
)
from admin.services.user_admin_service import (
    delete_admin_user,
    get_admin_user,
    link_signup_invitee,
    list_admin_users,
    update_admin_user,
)
from admin.services.user_export_service import build_users_csv
from config.constants import AppRole, UserStatus
from config.db.session import get_db
from core.dependencies import AdminReadUser, AdminWriteUser
from core.utils.roles import load_user_roles

router = APIRouter()


@router.get("", response_model=AdminUserListResponse, summary="Elenco utenti")
def get_admin_users(
    actor: AdminReadUser,
    db: Session = Depends(get_db),
    q: str | None = Query(default=None, max_length=64, description="Nome, username o email."),
    status: UserStatus | None = Query(default=None),
    role: AppRole | None = Query(default=None),
    invited_only: bool = Query(default=False),
    sort: AdminUserSort = Query(default=AdminUserSort.CREATED_AT),
    order: SortOrder = Query(default=SortOrder.DESC),
    limit: int = Query(default=30, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> AdminUserListResponse:
    """Lista globale account. Lettura: admin e super_admin."""
    try:
        return list_admin_users(
            db,
            query=q,
            status=status,
            role=role,
            invited_only=invited_only,
            limit=limit,
            offset=offset,
            include_pending_reason=AppRole.SUPER_ADMIN.value in load_user_roles(db, actor.id),
            sort=sort,
            order=order,
        )
    except SQLAlchemyError as exc:
        raise http_error_admin_internal("Unable to list users") from exc


@router.post(
    "/export",
    summary="Esporta utenti CSV",
    responses={200: {"content": {"text/csv": {}}, "description": "File CSV"}},
)
def export_admin_users(
    body: ExportAdminUsersRequest,
    actor: AdminWriteUser,
    db: Session = Depends(get_db),
) -> Response:
    """Export globale, colonne custom o mailing list. Scrittura: solo super_admin."""
    try:
        payload, filename = build_users_csv(
            db,
            actor=actor,
            mode=body.mode,
            columns=body.columns,
        )
    except AdminServiceError as exc:
        raise http_error_from_admin(exc) from exc
    except SQLAlchemyError as exc:
        raise http_error_admin_internal("Unable to export users") from exc
    return Response(
        content=payload,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/{user_id}", response_model=AdminUserDetail, summary="Dettaglio utente")
def get_admin_user_detail(
    actor: AdminReadUser,
    db: Session = Depends(get_db),
    user_id: uuid.UUID = Path(),
) -> AdminUserDetail:
    """Dettaglio account + metriche. Lettura: admin e super_admin."""
    try:
        detail = get_admin_user(db, user_id)
        if AppRole.SUPER_ADMIN.value not in load_user_roles(db, actor.id):
            detail.pending_reason = None
        return detail
    except AdminServiceError as exc:
        raise http_error_from_admin(exc) from exc
    except SQLAlchemyError as exc:
        raise http_error_admin_internal("Unable to load user") from exc


@router.post(
    "/{user_id}/invitees",
    response_model=AdminUserDetail,
    summary="Collega un invitato",
)
def post_admin_user_invitee(
    body: LinkAdminSignupInviteRequest,
    actor: AdminWriteUser,
    db: Session = Depends(get_db),
    user_id: uuid.UUID = Path(),
) -> AdminUserDetail:
    """Attribuisce l'invito signup e crea la connessione accepted. Scrittura: solo super_admin."""
    try:
        return link_signup_invitee(db, actor=actor, inviter_id=user_id, invitee_id=body.invitee_id)
    except AdminServiceError as exc:
        raise http_error_from_admin(exc) from exc
    except SQLAlchemyError as exc:
        raise http_error_admin_internal("Unable to link signup invite") from exc


@router.patch("/{user_id}", response_model=AdminUserDetail, summary="Aggiorna utente")
def patch_admin_user(
    body: UpdateAdminUserRequest,
    actor: AdminWriteUser,
    db: Session = Depends(get_db),
    user_id: uuid.UUID = Path(),
) -> AdminUserDetail:
    """Stato e ruoli. Scrittura: solo super_admin."""
    try:
        return update_admin_user(db, actor=actor, user_id=user_id, status=body.status, roles=body.roles)
    except AdminServiceError as exc:
        raise http_error_from_admin(exc) from exc
    except SQLAlchemyError as exc:
        raise http_error_admin_internal("Unable to update user") from exc


@router.delete("/{user_id}", response_model=AdminUserDeletedResponse, summary="Elimina utente")
def delete_admin_user_account(
    actor: AdminWriteUser,
    db: Session = Depends(get_db),
    user_id: uuid.UUID = Path(),
) -> AdminUserDeletedResponse:
    """Rimuove l'account dal DB. Scrittura: solo super_admin."""
    try:
        return delete_admin_user(db, actor=actor, user_id=user_id)
    except AdminServiceError as exc:
        raise http_error_from_admin(exc) from exc
    except SQLAlchemyError as exc:
        raise http_error_admin_internal("Unable to delete user") from exc
