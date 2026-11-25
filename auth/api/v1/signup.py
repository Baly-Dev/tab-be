"""F1 — signup atomico (wizard FE: un solo payload a fine flusso)."""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, Request, Security, status
from fastapi.security import HTTPAuthorizationCredentials
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

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
from auth.utils.registration import (
    is_email_password_pending_user,
    is_oauth_pending_user,
    is_registration_complete,
)
from config import AppRole, UserStatus
from config.db.session import get_db
from core.models.interest import CoreInterest
from core.models.profile import CoreProfile
from core.models.user_interest import CoreUserInterest
from core.models.user_role import CoreUserRole
from notifications.services.profile_incomplete import sync_profile_incomplete_notification
from services.brevo import BrevoService, get_brevo_service

router = APIRouter()


def _validate_interest_ids(db: Session, interest_ids: list[uuid.UUID]) -> None:
    """Verifica che tutti gli interessi esistano e siano attivi (lista vuota ammessa)."""
    if not interest_ids:
        return
    found = db.scalars(
        select(CoreInterest.id).where(
            CoreInterest.id.in_(interest_ids),
            CoreInterest.is_active.is_(True),
        )
    ).all()
    if len(found) != len(interest_ids):
        raise http_error_invalid_interest_ids()


def _resolve_invited_by_id(db: Session, inviter_code: str | None) -> uuid.UUID | None:
    """Risolve codice invito opzionale (solo connector+ attivi)."""
    return resolve_inviter_id(db, inviter_code)


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
    for key, value in _profile_kwargs_from_signup(body, profile.user_id).items():
        if key == "user_id":
            continue
        setattr(profile, key, value)


def _optional_bearer_user(
    request: Request,
    credentials: Annotated[
        HTTPAuthorizationCredentials | None,
        Security(bearer_scheme),
    ],
    db: Session,
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
    return user_from_access_token(raw, db, require_active=False)


def _complete_oauth_signup(
    db: Session,
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
    if not is_oauth_pending_user(user):
        raise http_error_signup_not_allowed()
    if is_registration_complete(db, user.id):
        raise http_error_registration_already_complete()

    if invited_by_id is not None and invited_by_id != user.id and user.invited_by_id is None:
        user.invited_by_id = invited_by_id

    if body.username.strip().lower() != str(user.username).strip().lower():
        conflict = db.scalar(
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

    profile = db.get(CoreProfile, user.id)
    if profile is None:
        db.add(CoreProfile(**_profile_kwargs_from_signup(body, user.id)))
    else:
        _apply_profile_fields(profile, body)
        db.add(profile)

    has_member_role = db.scalar(
        select(CoreUserRole.id).where(
            CoreUserRole.user_id == user.id,
            CoreUserRole.role == AppRole.MEMBER,
        )
    )
    if has_member_role is None:
        db.add(CoreUserRole(user_id=user.id, role=AppRole.MEMBER))

    for iid in body.interest_ids:
        db.add(CoreUserInterest(user_id=user.id, interest_id=iid))

    connect_signup_inviter(db, user)

    from admin.services.audit_log import record_audit
    from config.constants import AuditModule

    record_audit(
        db,
        module=AuditModule.AUTH,
        action="user.signed_up",
        message=f"Nuovo account @{user.username}",
        actor=user,
        target_type="user",
        target_id=user.id,
        payload={"username": str(user.username)},
    )
    sync_profile_incomplete_notification(db, user)

    try:
        db.commit()
    except IntegrityError:
        db.rollback()
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
def signup(
    body: SignupRequest,
    request: Request,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    brevo: BrevoService = Depends(get_brevo_service),
    credentials: Annotated[
        HTTPAuthorizationCredentials | None,
        Security(bearer_scheme),
    ] = None,
) -> SignupResponse:
    """Wizard finale: nuovo utente email/password oppure completamento OAuth ``PENDING``."""
    invited_by_id = _resolve_invited_by_id(db, body.inviter_referral_code)
    _validate_interest_ids(db, body.interest_ids)
    token_user = _optional_bearer_user(request, credentials, db)

    existing = db.scalar(select(AuthUser).where(AuthUser.email == body.email))
    if existing is not None:
        if existing.status == UserStatus.ACTIVE:
            raise http_error_email_or_username_taken()
        if is_email_password_pending_user(existing):
            raise http_error_email_verification_pending()
        if is_oauth_pending_user(existing):
            return _complete_oauth_signup(
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
        db.flush()
    except IntegrityError:
        db.rollback()
        raise http_error_email_or_username_taken() from None

    db.add(CoreProfile(**_profile_kwargs_from_signup(body, user.id)))
    db.add(CoreUserRole(user_id=user.id, role=AppRole.MEMBER))
    for iid in body.interest_ids:
        db.add(CoreUserInterest(user_id=user.id, interest_id=iid))

    try:
        db.commit()
    except IntegrityError:
        db.rollback()
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
