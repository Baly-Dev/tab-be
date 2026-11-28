"""Login, refresh access token e logout (refresh revocabile)."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Request, Security
from fastapi.security import HTTPAuthorizationCredentials
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

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
)
from auth.utils.rate_limit import (
    clear_login_identifier_limits,
    enforce_login_limits,
    require_ip_limit,
)
from auth.utils.session import build_token_response
from core.utils.roles import load_user_roles
from auth.utils.tokens import (
    create_access_token,
    find_valid_refresh_row,
    revoke_refresh_plain,
    rotate_refresh_token,
)
from config import UserStatus
from config.db import get_async_db

router = APIRouter()


@router.post("/login", response_model=TokenResponse)
async def login(body: LoginRequest, request: Request, db: AsyncSession = Depends(get_async_db)) -> TokenResponse:
    """Credenziali valide → access JWT (breve) + refresh opaco (lungo, in DB solo hash)."""
    ident = normalize_login_identifier(body.identifier)
    await enforce_login_limits(request, ident)
    user = await db.scalar(
        select(AuthUser).where(
            or_(AuthUser.email == ident, AuthUser.username == ident),
        )
    )
    if user is None or not user.has_password or not user.verify_password(body.password):
        raise http_error_invalid_credentials()

    upgrade_password_hash_if_needed(user, body.password)

    raise_if_cannot_login(user)

    try:
        token_response = await build_token_response(db, user)
    except ValueError:
        raise http_error_auth_not_configured() from None
    await db.commit()
    await clear_login_identifier_limits(ident)
    return token_response


@router.post("/refresh", response_model=TokenResponse)
async def refresh_tokens(
    body: RefreshRequest,
    db: AsyncSession = Depends(get_async_db),
    _: None = Depends(require_ip_limit("refresh")),
) -> TokenResponse:
    """Scambia refresh valido con nuova coppia (rotazione refresh)."""
    plain = body.refresh_token.strip()
    rotated = await rotate_refresh_token(db, plain)
    if rotated is None:
        raise http_error_invalid_refresh_token()
    _row, new_refresh_plain, user = rotated
    if user.status != UserStatus.ACTIVE or user.email_verified_at is None:
        await revoke_refresh_plain(db, new_refresh_plain)
        await db.commit()
        raise http_error_account_inactive()
    roles = await load_user_roles(db, user.id)
    try:
        access, expires_in = create_access_token(
            user_id=user.id,
            email=str(user.email),
            roles=roles,
        )
    except ValueError:
        await db.rollback()
        raise http_error_auth_not_configured() from None
    await db.commit()
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
async def logout(
    body: LogoutRequest,
    credentials: Annotated[HTTPAuthorizationCredentials, Security(bearer_scheme_required)],
    db: AsyncSession = Depends(get_async_db),
) -> LogoutResponse:
    """Protetta: Authorize con access_token (JWT) + body con refresh_token opaco."""
    user = await user_from_access_token(credentials.credentials, db)
    plain = body.refresh_token.strip()
    if plain.count(".") == 2:
        raise http_error_logout_wrong_token_type()
    row = await find_valid_refresh_row(db, plain)
    if row is not None and row.user_id != user.id:
        raise http_error_refresh_token_forbidden()
    await revoke_refresh_plain(db, plain)
    await db.commit()
    return LogoutResponse()