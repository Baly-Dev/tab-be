"""Signup: new email/password account, or finish a pending OAuth account."""

from __future__ import annotations

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
from auth.utils.registration import (
    is_email_password_pending_user,
    is_oauth_pending_user,
    is_registration_complete,
)
from auth.utils.roles import ensure_member_role
from config import UserStatus
from config.db.session import get_db
from services.brevo import BrevoService, get_brevo_service

router = APIRouter()


def _optional_bearer_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None,
    db: Session,
) -> AuthUser | None:
    """Bearer user when present (PENDING allowed so OAuth signup can finish)."""
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
    token_user: AuthUser | None,
    background_tasks: BackgroundTasks,
    brevo: BrevoService,
) -> SignupResponse:
    if token_user is not None and token_user.id != user.id:
        raise http_error_signup_token_mismatch()
    if not is_oauth_pending_user(user):
        raise http_error_signup_not_allowed()
    if is_registration_complete(db, user.id):
        raise http_error_registration_already_complete()

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
    user.first_name = body.first_name
    user.last_name = body.last_name
    user.status = UserStatus.ACTIVE
    db.add(user)
    ensure_member_role(db, user.id)

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
    """New email/password user, or completion of an OAuth ``PENDING`` account."""
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
        first_name=body.first_name,
        last_name=body.last_name,
        password_hash=hash_password(body.password),
        status=UserStatus.PENDING,
    )
    db.add(user)

    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise http_error_email_or_username_taken() from None

    ensure_member_role(db, user.id)

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
