"""Controlli stato account prima di emettere una sessione."""

from __future__ import annotations

from auth.errors.login_errors import (
    http_error_account_deleted,
    http_error_account_inactive,
    http_error_account_suspended,
    http_error_email_not_verified,
)
from auth.models.user import AuthUser
from config import UserStatus


def raise_if_cannot_login(user: AuthUser) -> None:
    """Stessi vincoli di POST /login (verifica email, sospeso, cancellato, inattivo)."""
    if user.status == UserStatus.PENDING or user.email_verified_at is None:
        raise http_error_email_not_verified()
    if user.status == UserStatus.SUSPENDED:
        raise http_error_account_suspended()
    if user.status == UserStatus.DELETED:
        raise http_error_account_deleted()
    if user.status != UserStatus.ACTIVE:
        raise http_error_account_inactive()
