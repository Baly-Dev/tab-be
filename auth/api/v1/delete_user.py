"""Cancellazione utente e dati collegati (profilo, ruoli, interessi, …)."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from auth.errors import http_error_user_not_found
from auth.errors.account_errors import http_error_delete_account_failed
from auth.models.user import AuthUser
from auth.schemas.delete_user import DeleteUserResponse
from auth.utils.account_purge import AccountPurgeError, purge_auth_user
from config.db.session import get_db

router = APIRouter()


@router.delete("/users/{user_id}", response_model=DeleteUserResponse)
def delete_user(user_id: uuid.UUID, db: Session = Depends(get_db)) -> DeleteUserResponse:
    """Elimina l'utente; profilo, ruoli, interessi e FK collegate seguono CASCADE."""
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
