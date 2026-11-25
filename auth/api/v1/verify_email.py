"""Conferma email (JWT) e re-invio invito via Brevo."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import jwt
from fastapi import APIRouter, BackgroundTasks, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from auth.errors import (
    http_error_auth_not_configured,
    http_error_invalid_verification_token,
    http_error_user_not_found,
    http_error_verification_link_expired,
    http_error_verification_not_configured,
    http_error_verification_token_mismatch,
)
from auth.models.user import AuthUser
from auth.schemas.verify_email import (
    ResendVerificationRequest,
    ResendVerificationResponse,
    VerifyEmailRequest,
    VerifyEmailResponse,
)
from auth.utils.session import build_token_response
from auth.utils.tokens import decode_email_verify_token
from config import UserStatus
from config.db.session import get_db
from services.brevo import BrevoService, get_brevo_service

router = APIRouter()


@router.post("/verify-email", response_model=VerifyEmailResponse)
def verify_email(
    body: VerifyEmailRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    brevo: BrevoService = Depends(get_brevo_service),
) -> VerifyEmailResponse:
    try:
        payload = decode_email_verify_token(body.token.strip())
    except ValueError:
        raise http_error_verification_not_configured() from None
    except jwt.ExpiredSignatureError:
        raise http_error_verification_link_expired() from None
    except jwt.PyJWTError:
        raise http_error_invalid_verification_token() from None

    try:
        uid = uuid.UUID(payload["sub"])
    except (KeyError, ValueError) as exc:
        raise http_error_invalid_verification_token() from exc

    email_claim = (payload.get("email") or "").strip().lower()
    user = db.get(AuthUser, uid)
    if user is None:
        raise http_error_user_not_found()

    if str(user.email).strip().lower() != email_claim:
        raise http_error_verification_token_mismatch()

    already_verified = user.email_verified_at is not None
    first_name = ""
    if not already_verified:
        user.email_verified_at = datetime.now(tz=UTC)
        user.status = UserStatus.ACTIVE
        db.add(user)
        first_name = str(user.first_name or "")

    verify_status = "already_verified" if already_verified else "verified"
    try:
        token_response = build_token_response(db, user)
    except ValueError:
        db.rollback()
        raise http_error_auth_not_configured() from None

    db.commit()
    if not already_verified:
        background_tasks.add_task(
            brevo.send_welcome_email_task,
            str(user.email),
            first_name,
        )
    return VerifyEmailResponse(status=verify_status, **token_response.model_dump())


@router.post("/resend-verification-email", response_model=ResendVerificationResponse)
def resend_verification_email(
    body: ResendVerificationRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    brevo: BrevoService = Depends(get_brevo_service),
) -> ResendVerificationResponse:
    """Risposta neutra; invia solo se utente esiste, PENDING e email non ancora verificata."""
    email_norm = body.email.strip().lower()
    user = db.scalar(select(AuthUser).where(AuthUser.email == email_norm))
    if (
        user is None
        or user.email_verified_at is not None
        or user.status != UserStatus.PENDING
    ):
        return ResendVerificationResponse(status="accepted")

    first_name = str(user.first_name or "")

    background_tasks.add_task(
        brevo.send_verification_email_task,
        str(user.id),
        str(user.email),
        first_name,
    )
    return ResendVerificationResponse(status="accepted")
