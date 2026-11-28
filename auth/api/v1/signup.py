"""F1 — signup atomico (wizard FE: un solo payload a fine flusso)."""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, Request, Security, status
from fastapi.security import HTTPAuthorizationCredentials
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from auth.errors import (
    http_error_account_cannot_register,
    http_error_email_or_username_taken,
    http_error_email_verification_pending,
    http_error_invalid_interest_ids,
    http_error_password_required,
    http_error_registration_already_complete,
    http_error_signup_not_allowed,
    http_error_signup_token_mismatch,
    http_error_username_taken,
)
from auth.models.user import AuthUser
from auth.schemas.signup import SignupRequest, SignupResponse
from auth.utils import hash_password
from auth.utils.helpers import bearer_scheme, user_from_access_token
from auth.utils.invites import connect_signup_inviter, resolve_inviter_id
from auth.utils.rate_limit import enforce_signup_limits
from auth.utils.registration import is_registration_complete
from config import AppRole, UserStatus
from config.db import get_async_db
from core.models.interest import CoreInterest
from core.models.profile import CoreProfile
from core.models.user_interest import CoreUserInterest
from core.models.user_role import CoreUserRole
from services.brevo import BrevoService, get_brevo_service

router = APIRouter()


async def _validate_interest_ids(db: AsyncSession, interest_ids: list[uuid.UUID]) -> None:
    """Verifica che tutti gli interessi esistano e siano attivi (lista vuota ammessa)."""
    if not interest_ids:
        return
    found = (await db.scalars(
        select(CoreInterest.id).where(
            CoreInterest.id.in_(interest_ids),
            CoreInterest.is_active.is_(True),
        )
    )).all()
    if len(found) != len(interest_ids):
        raise http_error_invalid_interest_ids()


async def _resolve_invited_by_id(db: AsyncSession, inviter_code: str | None) -> uuid.UUID | None:
    """Risolve codice invito opzionale (professional, admin, super_admin attivi)."""
    return await resolve_inviter_id(db, inviter_code)


def _profile_kwargs_from_signup(body: SignupRequest, user_id: uuid.UUID) -> dict:
    """Campi ``core_profiles`` dal payload signup."""
    return {
        "user_id": user_id,
        "first_name": body.first_name,
        "last_name": body.last_name,
        "birth_date": body.birth_date,
        "gender": body.gender.value,
        "marketing_consent": body.marketing_consent,
        "residence_country": body.residence_country,
        "residence_city": body.residence_city,
        "bio": body.bio,
        "avatar_url": body.avatar_url,
        "current_company_name": body.current_company_name,
        "current_job_position": body.current_job_position,
        "linkedin_url": body.linkedin_url,
    }


def _apply_profile_fields(profile: CoreProfile, body: SignupRequest) -> None:
    """Aggiorna profilo esistente con i dati del wizard."""
    kwargs = _profile_kwargs_from_signup(body, profile.user_id)
    profile.apply_patch({k: v for k, v in kwargs.items() if k != "user_id"})


async def _optional_bearer_user(
    request: Request,
    credentials: Annotated[
        HTTPAuthorizationCredentials | None,
        Security(bearer_scheme),
    ],
    db: AsyncSession,
) -> AuthUser | None:
    """Utente da Bearer se presente (consente PENDING per completamento OAuth)."""
    raw: str | None = None
    if credentials is not None and credentials.scheme.lower() == "bearer":
        raw = credentials.credentials.strip() or None
    if not raw:
        auth_header = request.headers.get("Authorization") or request.headers.get("authorization")
        if auth_header and auth_header.lower().startswith("bearer "):
            raw = auth_header[7:].strip() or None
    if not raw:
        return None
    return await user_from_access_token(raw, db, require_active=False)


async def _complete_oauth_signup(
    db: AsyncSession,
    user: AuthUser,
    body: SignupRequest,
    invited_by_id: uuid.UUID | None,
    token_user: AuthUser | None,
    background_tasks: BackgroundTasks,
    brevo: BrevoService,
) -> SignupResponse:
    """Completa wizard per utente OAuth ``PENDING`` → ``ACTIVE``."""
    if token_user is not None and token_user.id != user.id:
        raise http_error_signup_token_mismatch()
    if not user.is_oauth_pending():
        raise http_error_signup_not_allowed()
    if await is_registration_complete(db, user.id):
        raise http_error_registration_already_complete()

    if invited_by_id is not None and invited_by_id != user.id and user.invited_by_id is None:
        user.invited_by_id = invited_by_id

    if body.username.strip().lower() != str(user.username).strip().lower():
        conflict = await db.scalar(
            select(AuthUser.id).where(
                AuthUser.username == body.username,
                AuthUser.id != user.id,
            )
        )
        if conflict is not None:
            raise http_error_username_taken()
        user.username = body.username

    if body.password is not None:
        user.password_hash = hash_password(body.password)
    user.status = UserStatus.ACTIVE
    db.add(user)

    profile = await db.get(CoreProfile, user.id)
    if profile is None:
        db.add(CoreProfile(**_profile_kwargs_from_signup(body, user.id)))
    else:
        _apply_profile_fields(profile, body)
        db.add(profile)

    has_member_role = await db.scalar(
        select(CoreUserRole.id).where(
            CoreUserRole.user_id == user.id,
            CoreUserRole.role == AppRole.PROFESSIONAL,
        )
    )
    if has_member_role is None:
        db.add(CoreUserRole(user_id=user.id, role=AppRole.PROFESSIONAL))

    for iid in body.interest_ids:
        db.add(CoreUserInterest(user_id=user.id, interest_id=iid))

    await connect_signup_inviter(db, user)

    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise http_error_email_or_username_taken() from None

    db.refresh(user)
    background_tasks.add_task(
        brevo.send_welcome_email_task,
        str(user.email),
        body.first_name,
    )
    return SignupResponse(
        id=user.id,
        email=str(user.email),
        username=str(user.username),
        status=user.status.value,
    )


@router.post("/signup", response_model=SignupResponse, status_code=status.HTTP_201_CREATED)
async def signup(
    body: SignupRequest,
    request: Request,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_async_db),
    brevo: BrevoService = Depends(get_brevo_service),
    credentials: Annotated[
        HTTPAuthorizationCredentials | None,
        Security(bearer_scheme),
    ] = None,
) -> SignupResponse:
    """Wizard finale: nuovo utente email/password oppure completamento OAuth ``PENDING``."""
    await enforce_signup_limits(request, body.email)
    invited_by_id = await _resolve_invited_by_id(db, body.inviter_referral_code)
    await _validate_interest_ids(db, body.interest_ids)
    token_user = await _optional_bearer_user(request, credentials, db)

    existing = await db.scalar(select(AuthUser).where(AuthUser.email == body.email))
    if existing is not None:
        if existing.status == UserStatus.ACTIVE:
            raise http_error_email_or_username_taken()
        if existing.is_email_password_pending():
            raise http_error_email_verification_pending()
        if existing.is_oauth_pending():
            return await _complete_oauth_signup(
                db,
                existing,
                body,
                invited_by_id,
                token_user,
                background_tasks,
                brevo,
            )
        raise http_error_account_cannot_register()

    if body.password is None:
        raise http_error_password_required()

    user = AuthUser(
        email=body.email,
        username=body.username,
        password_hash=hash_password(body.password),
        status=UserStatus.PENDING,
        invited_by_id=invited_by_id,
    )
    db.add(user)

    try:
        await db.flush()
    except IntegrityError:
        await db.rollback()
        raise http_error_email_or_username_taken() from None

    db.add(CoreProfile(**_profile_kwargs_from_signup(body, user.id)))
    db.add(CoreUserRole(user_id=user.id, role=AppRole.PROFESSIONAL))
    for iid in body.interest_ids:
        db.add(CoreUserInterest(user_id=user.id, interest_id=iid))

    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise http_error_email_or_username_taken() from None

    db.refresh(user)

    background_tasks.add_task(
        brevo.send_verification_email_task,
        str(user.id),
        str(user.email),
        body.first_name,
    )

    return SignupResponse(
        id=user.id,
        email=str(user.email),
        username=str(user.username),
        status=user.status.value,
    )
