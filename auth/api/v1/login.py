"""Login, refresh access token e logout (refresh revocabile)."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Security
from fastapi.security import HTTPAuthorizationCredentials
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from auth.errors import (
    http_error_account_inactive,
    http_error_auth_not_configured,
    http_error_invalid_credentials,
    http_error_invalid_refresh_token,
    http_error_logout_wrong_token_type,
    http_error_refresh_token_forbidden,
)
from auth.models.user import AuthUser
from auth.schemas.login import (
    AuthUserBrief,
    LoginRequest,
    LogoutRequest,
    LogoutResponse,
    RefreshRequest,
    TokenResponse,
    normalize_login_identifier,
)
from auth.utils.account_status import raise_if_cannot_login
from auth.utils.helpers import (
    bearer_scheme_required,
    upgrade_password_hash_if_needed,
    user_from_access_token,
    verify_password,
)
from auth.utils.session import build_token_response, load_user_roles
from auth.utils.tokens import (
    create_access_token,
    find_valid_refresh_row,
    revoke_refresh_plain,
    rotate_refresh_token,
)
from config import UserStatus
from config.db.session import get_db
from notifications.services.profile_incomplete import sync_profile_incomplete_notification

router = APIRouter()


@router.post("/login", response_model=TokenResponse)
def login(body: LoginRequest, db: Session = Depends(get_db)) -> TokenResponse:
    """Credenziali valide → access JWT (breve) + refresh opaco (lungo, in DB solo hash)."""
    ident = normalize_login_identifier(body.identifier)
    user = db.scalar(
        select(AuthUser).where(
            or_(AuthUser.email == ident, AuthUser.username == ident),
        )
    )
    if user is None or not user.password_hash or not verify_password(
        body.password, user.password_hash
    ):
        raise http_error_invalid_credentials()

    upgrade_password_hash_if_needed(user, body.password)

    raise_if_cannot_login(user)
    sync_profile_incomplete_notification(db, user)

    try:
        token_response = build_token_response(db, user)
    except ValueError:
        raise http_error_auth_not_configured() from None
    db.commit()
    return token_response


@router.post("/refresh", response_model=TokenResponse)
def refresh_tokens(body: RefreshRequest, db: Session = Depends(get_db)) -> TokenResponse:
    """Scambia refresh valido con nuova coppia (rotazione refresh)."""
    plain = body.refresh_token.strip()
    row = find_valid_refresh_row(db, plain)
    if row is None:
        raise http_error_invalid_refresh_token()
    user = db.get(AuthUser, row.user_id)
    if user is None:
        raise http_error_invalid_refresh_token()
    if user.status != UserStatus.ACTIVE or user.email_verified_at is None:
        raise http_error_account_inactive()

    rotated = rotate_refresh_token(db, plain)
    if rotated is None:
        raise http_error_invalid_refresh_token()
    _row, new_refresh_plain, user = rotated
    roles = load_user_roles(db, user.id)
    try:
        access, expires_in = create_access_token(
            user_id=user.id,
            email=str(user.email),
            roles=roles,
        )
    except ValueError:
        db.rollback()
        raise http_error_auth_not_configured() from None
    db.commit()
    return TokenResponse(
        access_token=access,
        refresh_token=new_refresh_plain,
        expires_in=expires_in,
        user=AuthUserBrief(
            id=user.id,
            email=str(user.email),
            username=str(user.username),
            status=user.status.value,
        ),
    )


@router.post("/logout", response_model=LogoutResponse)
def logout(
    body: LogoutRequest,
    credentials: Annotated[HTTPAuthorizationCredentials, Security(bearer_scheme_required)],
    db: Session = Depends(get_db),
) -> LogoutResponse:
    """Protetta: Authorize con access_token (JWT) + body con refresh_token opaco."""
    user = user_from_access_token(credentials.credentials, db)
    plain = body.refresh_token.strip()
    if plain.count(".") == 2:
        raise http_error_logout_wrong_token_type()
    row = find_valid_refresh_row(db, plain)
    if row is not None and row.user_id != user.id:
        raise http_error_refresh_token_forbidden()
    revoke_refresh_plain(db, plain)
    db.commit()
    return LogoutResponse()
