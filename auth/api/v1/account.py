"""Change password, deactivate, and delete the authenticated account."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

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
from auth.models.user_role import AuthUserRole
from auth.schemas.account import (
    ChangePasswordRequest,
    ChangePasswordResponse,
    DeactivateAccountRequest,
    DeactivateAccountResponse,
    DeleteAccountRequest,
    DeleteAccountResponse,
)
from auth.utils.account_purge import AccountPurgeError, purge_auth_user
from auth.utils.helpers import AuthenticatedUser, hash_password, verify_password
from auth.utils.roles import load_user_roles
from auth.utils.tokens import revoke_all_refresh_tokens_for_user
from config.constants import AppRole, UserStatus
from config.db.session import get_db

router = APIRouter()


@router.post(
    "/change-password",
    response_model=ChangePasswordResponse,
    summary="Change or set the password of the authenticated user",
)
def change_password(
    body: ChangePasswordRequest,
    user: AuthenticatedUser,
    db: Session = Depends(get_db),
) -> ChangePasswordResponse:
    """Updates ``password_hash`` and revokes every refresh token."""
    has_password = user.password_hash is not None

    if has_password:
        if not body.current_password:
            raise http_error_current_password_required()
        if not verify_password(body.current_password, str(user.password_hash)):
            raise http_error_wrong_current_password()

    user.password_hash = hash_password(body.new_password)
    db.add(user)
    revoke_all_refresh_tokens_for_user(db, user.id)

    try:
        db.commit()
    except Exception as exc:
        db.rollback()
        raise http_error_change_password_failed() from exc

    return ChangePasswordResponse()


def _confirm_account_password(user: AuthUser, password: str | None) -> None:
    if user.password_hash is None:
        return
    if not password:
        raise http_error_password_required_for_delete()
    if not verify_password(password, str(user.password_hash)):
        raise http_error_wrong_password_for_delete()


def _reject_last_super_admin(db: Session, user_id: uuid.UUID) -> None:
    if AppRole.SUPER_ADMIN.value not in load_user_roles(db, user_id):
        return
    others = db.scalar(
        select(func.count())
        .select_from(AuthUserRole)
        .join(AuthUser, AuthUser.id == AuthUserRole.user_id)
        .where(
            AuthUserRole.role == AppRole.SUPER_ADMIN,
            AuthUser.status == UserStatus.ACTIVE,
            AuthUserRole.user_id != user_id,
        )
    )
    if int(others or 0) == 0:
        raise http_error_last_super_admin()


@router.post(
    "/deactivate-account",
    response_model=DeactivateAccountResponse,
    summary="Deactivate the authenticated account",
)
def deactivate_my_account(
    body: DeactivateAccountRequest,
    user: AuthenticatedUser,
    db: Session = Depends(get_db),
) -> DeactivateAccountResponse:
    """Suspend the account and revoke sessions. The row stays until deletion."""
    _confirm_account_password(user, body.password)
    _reject_last_super_admin(db, user.id)

    user.status = UserStatus.SUSPENDED
    db.add(user)
    revoke_all_refresh_tokens_for_user(db, user.id)
    try:
        db.commit()
    except Exception as exc:
        db.rollback()
        raise http_error_deactivate_account_failed() from exc

    return DeactivateAccountResponse()


@router.post(
    "/delete-account",
    response_model=DeleteAccountResponse,
    summary="Delete the authenticated account",
)
def delete_my_account(
    body: DeleteAccountRequest,
    user: AuthenticatedUser,
    db: Session = Depends(get_db),
) -> DeleteAccountResponse:
    """Hard-delete: the user row is removed so email and username can be reused."""
    _confirm_account_password(user, body.password)
    _reject_last_super_admin(db, user.id)

    try:
        purge_auth_user(db, user)
        db.commit()
    except AccountPurgeError as exc:
        db.rollback()
        raise http_error_delete_account_failed() from exc
    except Exception as exc:
        db.rollback()
        raise http_error_delete_account_failed() from exc

    return DeleteAccountResponse(deleted=True)
