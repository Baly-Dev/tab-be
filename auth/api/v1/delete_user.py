"""Delete a user. Super admin only; related auth rows follow CASCADE."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from auth.errors import http_error_user_not_found
from auth.errors.account_errors import http_error_delete_account_failed
from auth.models.user import AuthUser
from auth.schemas.delete_user import DeleteUserResponse
from auth.utils.account_purge import AccountPurgeError, purge_auth_user
from auth.utils.helpers import AuthenticatedUser
from auth.utils.roles import load_user_roles
from config.constants import AppRole
from config.db.session import get_db

router = APIRouter()


@router.delete("/users/{user_id}", response_model=DeleteUserResponse)
def delete_user(
    user_id: uuid.UUID,
    actor: AuthenticatedUser,
    db: Session = Depends(get_db),
) -> DeleteUserResponse:
    """Delete the user. Roles, sessions, passkeys, and social links cascade."""
    if AppRole.SUPER_ADMIN.value not in load_user_roles(db, actor.id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"code": "forbidden", "message": "Super admin role required"},
        )
    user = db.get(AuthUser, user_id)
    if user is None:
        raise http_error_user_not_found()

    try:
        purge_auth_user(db, user)
        db.commit()
    except AccountPurgeError as exc:
        db.rollback()
        raise http_error_delete_account_failed() from exc

    return DeleteUserResponse(user_id=user_id)
