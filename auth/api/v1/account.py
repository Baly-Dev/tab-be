"""Cambio password e cancellazione account (utente autenticato)."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from auth.errors.account_errors import (
    http_error_change_password_failed,
    http_error_current_password_required,
    http_error_deactivate_account_failed,
    http_error_delete_account_failed,
    http_error_last_super_admin,
    http_error_password_required_for_delete,
    http_error_wrong_current_password,
    http_error_wrong_password_for_delete,
)
from auth.models.user import AuthUser
from auth.schemas.account import (
    ChangePasswordRequest,
    ChangePasswordResponse,
    DeactivateAccountRequest,
    DeactivateAccountResponse,
    DeleteAccountRequest,
    DeleteAccountResponse,
)
from auth.utils.account_purge import AccountPurgeError, purge_auth_user
from auth.utils.helpers import AuthenticatedUser, hash_password
from auth.utils.tokens import revoke_all_refresh_tokens_for_user
from config.constants import AppRole, UserStatus
from config.db import get_async_db
from core.models.user_role import CoreUserRole
from core.utils.roles import load_user_roles

router = APIRouter()


@router.post(
    "/change-password",
    response_model=ChangePasswordResponse,
    summary="Cambia o imposta la password dell'utente autenticato",
)
async def change_password(
    body: ChangePasswordRequest,
    user: AuthenticatedUser,
    db: AsyncSession = Depends(get_async_db),
) -> ChangePasswordResponse:
    """Aggiorna ``password_hash`` e revoca tutti i refresh token (ri-login richiesto)."""
    if user.has_password:
        if not body.current_password:
            raise http_error_current_password_required()
        if not user.verify_password(body.current_password):
            raise http_error_wrong_current_password()
    # OAuth-only: current_password non richiesta

    user.password_hash = hash_password(body.new_password)
    db.add(user)
    await revoke_all_refresh_tokens_for_user(db, user.id)

    try:
        await db.commit()
    except Exception as exc:
        await db.rollback()
        raise http_error_change_password_failed() from exc

    return ChangePasswordResponse()


def _confirm_account_password(user: AuthUser, password: str | None) -> None:
    """Password obbligatoria solo se l'account ne ha una."""
    if not user.has_password:
        return
    if not password:
        raise http_error_password_required_for_delete()
    if not user.verify_password(password):
        raise http_error_wrong_password_for_delete()


async def _reject_last_super_admin(db: AsyncSession, user_id: uuid.UUID) -> None:
    """Evita di chiudere l'unico super admin ancora attivo."""
    if AppRole.SUPER_ADMIN.value not in await load_user_roles(db, user_id):
        return
    others = await db.scalar(
        select(func.count())
        .select_from(CoreUserRole)
        .join(AuthUser, AuthUser.id == CoreUserRole.user_id)
        .where(
            CoreUserRole.role == AppRole.SUPER_ADMIN,
            AuthUser.status == UserStatus.ACTIVE,
            CoreUserRole.user_id != user_id,
        )
    )
    if int(others or 0) == 0:
        raise http_error_last_super_admin()


@router.post(
    "/deactivate-account",
    response_model=DeactivateAccountResponse,
    summary="Disattiva l'account dell'utente autenticato",
)
async def deactivate_my_account(
    body: DeactivateAccountRequest,
    user: AuthenticatedUser,
    db: AsyncSession = Depends(get_async_db),
) -> DeactivateAccountResponse:
    """Sospende l'account e revoca le sessioni. I dati restano finché non si elimina."""
    _confirm_account_password(user, body.password)
    await _reject_last_super_admin(db, user.id)

    user.status = UserStatus.SUSPENDED
    db.add(user)
    await revoke_all_refresh_tokens_for_user(db, user.id)
    try:
        await db.commit()
    except Exception as exc:
        await db.rollback()
        raise http_error_deactivate_account_failed() from exc

    return DeactivateAccountResponse()


@router.post(
    "/delete-account",
    response_model=DeleteAccountResponse,
    summary="Cancella l'account dell'utente autenticato",
)
async def delete_my_account(
    body: DeleteAccountRequest,
    user: AuthenticatedUser,
    db: AsyncSession = Depends(get_async_db),
) -> DeleteAccountResponse:
    """Hard-delete: rimuove l'utente dal DB (email/username liberi per una nuova iscrizione)."""
    _confirm_account_password(user, body.password)
    await _reject_last_super_admin(db, user.id)

    try:
        await purge_auth_user(db, user)
        await db.commit()
    except AccountPurgeError as exc:
        await db.rollback()
        raise http_error_delete_account_failed() from exc
    except Exception as exc:
        await db.rollback()
        raise http_error_delete_account_failed() from exc

    return DeleteAccountResponse(deleted=True)
