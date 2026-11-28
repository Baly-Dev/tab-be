"""JWT (access, verifica email) e refresh token opachi (hash su ``auth_refresh_token``)."""

from __future__ import annotations

import hashlib
import hmac
import secrets
import uuid
from datetime import UTC, datetime, timedelta

import jwt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from typing import TYPE_CHECKING

from auth.models.password_reset_token import AuthPasswordResetToken
from auth.models.user import AuthUser
from config import Settings, get_settings

if TYPE_CHECKING:
    from auth.utils.sessions.refresh_session import RefreshTokenRecord

ALG = "HS256"
TOKEN_TYP_EMAIL_VERIFY = "email_verify"
TOKEN_TYP_ACCESS = "access"


def _require_secret() -> str:
    secret = get_settings().jwt_secret.strip()
    if not secret:
        raise ValueError("JWT_SECRET is not configured")
    return secret


# --- Email verification (JWT) ---


def create_email_verify_token(user_id: uuid.UUID, email: str) -> str:
    settings = get_settings()
    now = datetime.now(tz=UTC)
    exp = now + timedelta(hours=settings.email_verify_token_expire_hours)
    payload = {
        "sub": str(user_id),
        "email": email.strip().lower(),
        "typ": TOKEN_TYP_EMAIL_VERIFY,
        "iat": int(now.timestamp()),
        "exp": int(exp.timestamp()),
    }
    return jwt.encode(payload, _require_secret(), algorithm=ALG)


def decode_email_verify_token(token: str) -> dict:
    payload = jwt.decode(
        token,
        _require_secret(),
        algorithms=[ALG],
        options={"require": ["exp", "sub", "email", "typ"]},
    )
    if payload.get("typ") != TOKEN_TYP_EMAIL_VERIFY:
        raise jwt.InvalidTokenError("wrong token type")
    return payload


# --- Access token (JWT) ---


def create_access_token(
    *,
    user_id: uuid.UUID,
    email: str,
    roles: list[str],
) -> tuple[str, int]:
    """Ritorna (jwt, expires_in secondi)."""
    settings = get_settings()
    now = datetime.now(tz=UTC)
    expires_in = settings.jwt_access_token_expire_minutes * 60
    exp = now + timedelta(seconds=expires_in)
    payload = {
        "sub": str(user_id),
        "email": email.strip().lower(),
        "typ": TOKEN_TYP_ACCESS,
        "roles": roles,
        "iat": int(now.timestamp()),
        "exp": int(exp.timestamp()),
    }
    token = jwt.encode(payload, _require_secret(), algorithm=ALG)
    return token, expires_in


def decode_access_token(token: str) -> dict:
    payload = jwt.decode(
        token,
        _require_secret(),
        algorithms=[ALG],
        options={"require": ["exp", "sub", "email", "typ"]},
    )
    if payload.get("typ") != TOKEN_TYP_ACCESS:
        raise jwt.InvalidTokenError("wrong token type")
    return payload


# --- Refresh token (opaque; store Redis o Postgres via ``RefreshSessionService``) ---


def generate_refresh_token_plain() -> str:
    """Token casuale inviato al client (non salvare in chiaro nel DB)."""
    return secrets.token_urlsafe(32)


def hash_refresh_token(plain: str, *, settings: Settings | None = None) -> str:
    """HMAC-SHA256 del refresh token con ``JWT_SECRET`` come pepper."""
    s = settings or get_settings()
    secret = s.jwt_secret.strip()
    if not secret:
        raise ValueError("JWT_SECRET is not configured")
    return hmac.new(secret.encode(), plain.encode(), hashlib.sha256).hexdigest()


def _refresh_sessions():
    from auth.utils.sessions.refresh_session import get_refresh_session_service

    return get_refresh_session_service()


async def persist_refresh_token(
    db: AsyncSession,
    *,
    user_id: uuid.UUID,
    plain: str,
    settings: Settings | None = None,
) -> "RefreshTokenRecord":
    """Registra refresh (Redis o Postgres)."""
    _ = settings
    return await _refresh_sessions().persist(db, user_id=user_id, plain=plain)


async def find_valid_refresh_row(
    db: AsyncSession,
    plain: str,
    *,
    settings: Settings | None = None,
) -> "RefreshTokenRecord | None":
    """Sessione refresh valida per token plain, se esiste."""
    _ = settings
    return await _refresh_sessions().find_valid(db, plain=plain)


async def revoke_refresh_plain(
    db: AsyncSession,
    plain: str,
    *,
    settings: Settings | None = None,
) -> bool:
    """Revoca un refresh token; ritorna True se trovato e revocato."""
    _ = settings
    return await _refresh_sessions().revoke_plain(db, plain)


async def rotate_refresh_token(
    db: AsyncSession,
    plain: str,
    *,
    settings: Settings | None = None,
) -> "tuple[RefreshTokenRecord, str, AuthUser] | None":
    """Ruota refresh; None se invalido."""
    _ = settings
    return await _refresh_sessions().rotate(db, plain)


# --- Password reset token (opaque, DB) ---


async def persist_password_reset_token(
    db: AsyncSession,
    *,
    user_id: uuid.UUID,
    plain: str,
    settings: Settings | None = None,
) -> AuthPasswordResetToken:
    """Salva hash reset password; invalida token precedenti non usati per l'utente."""
    s = settings or get_settings()
    now = datetime.now(tz=UTC)
    for row in (
        await db.scalars(
            select(AuthPasswordResetToken).where(
                AuthPasswordResetToken.user_id == user_id,
                AuthPasswordResetToken.used_at.is_(None),
            )
        )
    ).all():
        row.mark_used(now)
        db.add(row)

    expires_at = now + timedelta(minutes=s.password_reset_token_expire_minutes)
    token_row = AuthPasswordResetToken(
        user_id=user_id,
        token_hash=hash_refresh_token(plain, settings=s),
        expires_at=expires_at,
    )
    db.add(token_row)
    await db.flush()
    return token_row


async def find_valid_password_reset_row(
    db: AsyncSession,
    plain: str,
    *,
    settings: Settings | None = None,
) -> AuthPasswordResetToken | None:
    """Riga reset valida (non usata, non scaduta)."""
    token_hash = hash_refresh_token(plain, settings=settings)
    now = datetime.now(tz=UTC)
    return await db.scalar(
        select(AuthPasswordResetToken).where(
            AuthPasswordResetToken.token_hash == token_hash,
            AuthPasswordResetToken.used_at.is_(None),
            AuthPasswordResetToken.expires_at > now,
        )
    )


async def mark_password_reset_used(db: AsyncSession, row: AuthPasswordResetToken) -> None:
    """Consuma il token monouso."""
    row.mark_used(datetime.now(tz=UTC))
    db.add(row)


async def revoke_all_refresh_tokens_for_user(db: AsyncSession, user_id: uuid.UUID) -> int:
    """Revoca tutte le sessioni refresh dell'utente; ritorna quante revocate."""
    return await _refresh_sessions().revoke_all_for_user(db, user_id)