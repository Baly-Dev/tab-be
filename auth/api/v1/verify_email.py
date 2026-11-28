"""Conferma email (JWT) e re-invio invito via Brevo."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import jwt
from fastapi import APIRouter, BackgroundTasks, Depends, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

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
from auth.utils.invites import connect_signup_inviter
from auth.utils.rate_limit import (
    allow_resend_verification_email,
    enforce_ip_limit,
    enforce_resend_verification_ip,
)
from auth.utils.session import build_token_response
from auth.utils.tokens import decode_email_verify_token
from config import UserStatus
from config.db import get_async_db
from core.models.profile import CoreProfile
from services.brevo import BrevoService, get_brevo_service

router = APIRouter()


@router.post("/verify-email", response_model=VerifyEmailResponse)
async def verify_email(
    body: VerifyEmailRequest,
    request: Request,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_async_db),
    brevo: BrevoService = Depends(get_brevo_service),
) -> VerifyEmailResponse:
    await enforce_ip_limit(request, "verify_email")
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
    user = await db.get(AuthUser, uid)
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
        await connect_signup_inviter(db, user)
        profile = await db.get(CoreProfile, user.id)
        first_name = profile.first_name if profile is not None else ""

    verify_status = "already_verified" if already_verified else "verified"
    try:
        token_response = await build_token_response(db, user)
    except ValueError:
        await db.rollback()
        raise http_error_auth_not_configured() from None

    await db.commit()
    if not already_verified:
        background_tasks.add_task(
            brevo.send_welcome_email_task,
            str(user.email),
            first_name,
        )
    return VerifyEmailResponse(status=verify_status, **token_response.model_dump())


@router.post("/resend-verification-email", response_model=ResendVerificationResponse)
async def resend_verification_email(
    body: ResendVerificationRequest,
    request: Request,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_async_db),
    brevo: BrevoService = Depends(get_brevo_service),
) -> ResendVerificationResponse:
    """Risposta neutra; invia solo se utente esiste, PENDING e email non ancora verificata."""
    await enforce_resend_verification_ip(request)
    email_norm = body.email.strip().lower()
    if not await allow_resend_verification_email(email_norm):
        return ResendVerificationResponse(status="accepted")
    user = await db.scalar(select(AuthUser).where(AuthUser.email == email_norm))
    if (
        user is None
        or user.email_verified_at is not None
        or user.status != UserStatus.PENDING
    ):
        return ResendVerificationResponse(status="accepted")

    profile = await db.get(CoreProfile, user.id)
    first_name = profile.first_name if profile is not None else ""

    background_tasks.add_task(
        brevo.send_verification_email_task,
        str(user.id),
        str(user.email),
        first_name,
    )
    return ResendVerificationResponse(status="accepted")
