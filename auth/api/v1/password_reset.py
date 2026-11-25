"""Forgot password e reset password (token monouso + email Brevo)."""

from __future__ import annotations

import logging

from fastapi import APIRouter, BackgroundTasks, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from auth.errors import (
    http_error_account_cannot_reset_password,
    http_error_auth_not_configured,
    http_error_invalid_reset_token,
    http_error_password_reset_not_configured,
    http_error_reset_password_failed,
)
from auth.models.user import AuthUser
from auth.schemas.password_reset import (
    ForgotPasswordRequest,
    ForgotPasswordResponse,
    ResetPasswordRequest,
    ResetPasswordResponse,
)
from auth.utils import hash_password
from auth.utils.session import build_token_response
from auth.utils.tokens import (
    count_recent_password_reset_requests,
    find_valid_password_reset_row,
    generate_refresh_token_plain,
    mark_password_reset_used,
    persist_password_reset_token,
    revoke_all_refresh_tokens_for_user,
)
from config import UserStatus, get_settings
from config.db.session import get_db
from services.brevo import send_password_reset_email_background

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/forgot-password", response_model=ForgotPasswordResponse)
def forgot_password(
    body: ForgotPasswordRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
) -> ForgotPasswordResponse:
    """Invia email con link se l'account ha password; risposta sempre generica."""
    settings = get_settings()
    user = db.scalar(select(AuthUser).where(AuthUser.email == body.email))

    if user is None:
        logger.info("Password reset skipped: no user for email")
        return ForgotPasswordResponse(status="accepted")

    if user.status in (UserStatus.SUSPENDED, UserStatus.DELETED):
        logger.info("Password reset skipped: user %s status=%s", user.id, user.status.value)
        return ForgotPasswordResponse(status="accepted")

    if user.password_hash is None:
        logger.info(
            "Password reset skipped: user %s has no password (OAuth-only account)",
            user.id,
        )
        return ForgotPasswordResponse(status="accepted")

    limit = settings.password_reset_rate_limit_per_hour
    if limit > 0 and count_recent_password_reset_requests(db, user.id, within_minutes=60) >= limit:
        logger.warning("Password reset rate limit reached for user %s", user.id)
        return ForgotPasswordResponse(status="accepted")

    plain = generate_refresh_token_plain()
    try:
        persist_password_reset_token(db, user_id=user.id, plain=plain)
        db.commit()
    except ValueError:
        db.rollback()
        raise http_error_password_reset_not_configured() from None

    first_name = str(user.first_name or "")
    logger.info("Password reset token created for user %s; queuing Brevo email", user.id)
    background_tasks.add_task(
        send_password_reset_email_background,
        body.email,
        plain,
        first_name,
    )

    return ForgotPasswordResponse(status="accepted")


@router.post("/reset-password", response_model=ResetPasswordResponse)
def reset_password(
    body: ResetPasswordRequest,
    db: Session = Depends(get_db),
) -> ResetPasswordResponse:
    """Imposta nuova password e restituisce token (auto-login, come verify-email)."""
    row = find_valid_password_reset_row(db, body.token.strip())
    if row is None:
        raise http_error_invalid_reset_token()

    user = db.get(AuthUser, row.user_id)
    if user is None:
        raise http_error_invalid_reset_token()

    if user.status in (UserStatus.SUSPENDED, UserStatus.DELETED):
        raise http_error_account_cannot_reset_password()

    user.password_hash = hash_password(body.password)
    db.add(user)
    mark_password_reset_used(db, row)
    revoke_all_refresh_tokens_for_user(db, user.id)

    try:
        token_response = build_token_response(db, user)
    except ValueError:
        db.rollback()
        raise http_error_auth_not_configured() from None

    try:
        db.commit()
    except Exception as exc:
        db.rollback()
        raise http_error_reset_password_failed() from exc

    return ResetPasswordResponse(status="password_reset", **token_response.model_dump())
