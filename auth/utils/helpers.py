"""Utility auth: password, dependency utente corrente (Bearer)."""

from __future__ import annotations

import uuid
from typing import Annotated

import jwt
from fastapi import Depends, Request, Security
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from auth.errors.session_errors import (
    http_error_access_token_expired,
    http_error_account_not_active,
    http_error_bearer_user_not_found,
    http_error_invalid_access_token,
    http_error_invalid_access_token_payload,
    http_error_not_authenticated,
    http_error_wrong_token_type,
)
from auth.models.user import AuthUser
from auth.utils.passwords import (
    hash_password,
    needs_rehash,
    upgrade_password_hash_if_needed,
    verify_password,
)
from auth.utils.tokens import decode_access_token
from config import UserStatus
from config.db import get_async_db

# Opzionale (auto_error=False): usato da get_current_user con fallback su Request.
bearer_scheme = HTTPBearer(
    scheme_name="BearerAuth",
    auto_error=False,
    description="JWT access_token da POST /api/v1/auth/login",
)

# Obbligatorio su route esplicite (logout): Swagger include Authorization nel curl.
bearer_scheme_required = HTTPBearer(
    scheme_name="BearerAuth",
    description="Incolla solo access_token (JWT) da login, senza refresh_token",
)


def _extract_bearer_token(authorization: str | None) -> str | None:
    if not authorization or not authorization.strip():
        return None
    text = authorization.strip()
    if text.lower().startswith("bearer "):
        token = text[7:].strip()
        return token or None
    return text


async def user_from_access_token(
    raw: str,
    db: AsyncSession,
    *,
    require_active: bool = True,
) -> AuthUser:
    """Valida JWT access e carica utente; se ``require_active``, solo ACTIVE."""
    token = raw.strip()
    if token.count(".") != 2:
        raise http_error_wrong_token_type()
    try:
        payload = decode_access_token(token)
    except jwt.ExpiredSignatureError:
        raise http_error_access_token_expired() from None
    except jwt.PyJWTError:
        raise http_error_invalid_access_token() from None

    try:
        uid = uuid.UUID(payload["sub"])
    except (KeyError, ValueError) as exc:
        raise http_error_invalid_access_token_payload() from exc

    user = await db.get(AuthUser, uid)
    if user is None:
        raise http_error_bearer_user_not_found()
    if user.status in (UserStatus.SUSPENDED, UserStatus.DELETED):
        raise http_error_account_not_active()
    if require_active and user.status != UserStatus.ACTIVE:
        raise http_error_account_not_active()
    return user


async def get_current_user(
    request: Request,
    credentials: Annotated[
        HTTPAuthorizationCredentials | None,
        Security(bearer_scheme),
    ] = None,
    db: AsyncSession = Depends(get_async_db),
) -> AuthUser:
    """Per route protette generiche: Bearer via Authorize o header Authorization."""
    raw: str | None = None
    if credentials is not None and credentials.scheme.lower() == "bearer":
        raw = credentials.credentials.strip() or None
    if not raw:
        for key in ("Authorization", "authorization"):
            raw = _extract_bearer_token(request.headers.get(key))
            if raw:
                break
    if not raw:
        raise http_error_not_authenticated(docs_hint=True)
    return await user_from_access_token(raw, db)


async def get_authenticated_user(
    request: Request,
    credentials: Annotated[
        HTTPAuthorizationCredentials | None,
        Security(bearer_scheme),
    ] = None,
    db: AsyncSession = Depends(get_async_db),
) -> AuthUser:
    """Bearer valido; consente ``PENDING`` (es. GET /core/me durante onboarding)."""
    raw: str | None = None
    if credentials is not None and credentials.scheme.lower() == "bearer":
        raw = credentials.credentials.strip() or None
    if not raw:
        for key in ("Authorization", "authorization"):
            raw = _extract_bearer_token(request.headers.get(key))
            if raw:
                break
    if not raw:
        raise http_error_not_authenticated()
    return await user_from_access_token(raw, db, require_active=False)


AuthenticatedUser = Annotated[AuthUser, Depends(get_current_user)]
AuthenticatedUserAllowPending = Annotated[AuthUser, Depends(get_authenticated_user)]

__all__ = [
    "AuthenticatedUser",
    "AuthenticatedUserAllowPending",
    "bearer_scheme",
    "bearer_scheme_required",
    "get_authenticated_user",
    "get_current_user",
    "hash_password",
    "needs_rehash",
    "upgrade_password_hash_if_needed",
    "user_from_access_token",
    "verify_password",
]