"""Redis fixed-window rate limits for auth routes and the API middleware.

Windows and prefixes come from ``settings.rate_limit``. Identity keys are hashed
so emails never sit in Redis as plaintext.
"""

from __future__ import annotations

import hashlib
import logging
from dataclasses import dataclass

from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse
from redis.exceptions import RedisError

from auth.errors.rate_limit_errors import (
    http_error_rate_limit_unavailable,
    http_error_rate_limited,
)
from config import RateLimitPolicy, RateLimitWindow, get_settings
from services.redis import get_async_redis_service

logger = logging.getLogger(__name__)

_API_EXEMPT_PATHS = frozenset(
    {"/health", "/docs", "/redoc", "/openapi.json", "/sentry-debug"}
)


@dataclass(frozen=True, slots=True)
class RateLimitHit:
    allowed: bool
    retry_after_seconds: int = 0


def client_ip(request: Request, *, policy: RateLimitPolicy | None = None) -> str:
    """Client address. ``X-Forwarded-For`` only when ``RATE_LIMIT_TRUST_X_FORWARDED_FOR``."""
    resolved = policy or get_settings().rate_limit
    if resolved.trust_x_forwarded_for:
        forwarded = (request.headers.get("x-forwarded-for") or "").split(",")[0].strip()
        if forwarded:
            return forwarded
        real_ip = (request.headers.get("x-real-ip") or "").strip()
        if real_ip:
            return real_ip
    host = request.client.host if request.client is not None else ""
    return host.strip() or "unknown"


async def enforce_login_limits(request: Request, identifier: str) -> None:
    """IP + identifier windows, plus optional identifier lockout. Before bcrypt."""
    policy = get_settings().rate_limit
    if not policy.enabled:
        return
    ident = _identity_key(identifier)
    ip = client_ip(request, policy=policy)
    await _raise_if_locked(policy, "login", ident)
    await _hit_or_raise(policy, "login:ip", ip, policy.login_ip)
    decision = await _hit(policy, "login:id", ident, policy.login_identifier)
    if not decision.allowed:
        await _set_lock(policy, "login", ident)
        raise http_error_rate_limited(decision.retry_after_seconds)


async def clear_login_identifier_limits(identifier: str) -> None:
    """Drop identifier counters after a successful password or passkey login."""
    policy = get_settings().rate_limit
    if not policy.enabled:
        return
    ident = _identity_key(identifier)
    await _delete_keys(
        policy,
        _counter_key(policy, "login:id", ident),
        _lock_key(policy, "login", ident),
    )


async def enforce_signup_limits(request: Request, email: str) -> None:
    policy = get_settings().rate_limit
    if not policy.enabled:
        return
    ip = client_ip(request, policy=policy)
    await _hit_or_raise(policy, "signup:ip", ip, policy.signup_ip)
    await _hit_or_raise(policy, "signup:email", _identity_key(email), policy.signup_email)


async def enforce_password_reset_ip(request: Request) -> None:
    """Forgot-password and reset-password: 429 by IP (token / email bombing)."""
    await enforce_ip_limit(request, "password_reset")


async def allow_password_reset_email(email: str) -> bool:
    """False = skip sending, still return the generic accepted body."""
    return await _allow_silent_identity("password_reset:email", email, "password_reset_email")


async def enforce_resend_verification_ip(request: Request) -> None:
    await enforce_ip_limit(request, "resend_verification")


async def allow_resend_verification_email(email: str) -> bool:
    return await _allow_silent_identity(
        "resend_verification:email",
        email,
        "resend_verification_email",
    )


async def enforce_ip_limit(request: Request, name: str) -> None:
    """Named per-IP bucket: oauth, passkey, handoff, verify_email, refresh, api, …"""
    policy = get_settings().rate_limit
    if not policy.enabled:
        return
    window = getattr(policy, f"{name}_ip", None)
    if not isinstance(window, RateLimitWindow):
        raise ValueError(f"Unknown rate-limit bucket: {name}")
    ip = client_ip(request, policy=policy)
    await _hit_or_raise(policy, f"{name}:ip", ip, window)


async def require_ip_limit(name: str):
    """FastAPI dependency for a named IP window."""

    async def _dependency(request: Request) -> None:
        await enforce_ip_limit(request, name)

    _dependency.__name__ = f"require_ip_limit_{name}"
    return _dependency


def should_limit_api_path(path: str) -> bool:
    """Global API limiter: ``/api/*`` except docs/health."""
    if path in _API_EXEMPT_PATHS:
        return False
    return path == "/api" or path.startswith("/api/")


async def reject_if_api_limited(request: Request) -> JSONResponse | None:
    """Middleware helper: 429/503 JSON, or None to continue."""
    if not should_limit_api_path(request.url.path):
        return None
    try:
        await enforce_ip_limit(request, "api")
    except HTTPException as exc:
        return JSONResponse(
            status_code=exc.status_code,
            content={"detail": exc.detail},
            headers=dict(exc.headers or {}),
        )
    return None


async def _allow_silent_identity(scope: str, value: str, window_attr: str) -> bool:
    policy = get_settings().rate_limit
    if not policy.enabled:
        return True
    window = getattr(policy, window_attr)
    decision = await _hit(policy, scope, _identity_key(value), window)
    return decision.allowed


async def _hit_or_raise(
    policy: RateLimitPolicy,
    scope: str,
    subject: str,
    window: RateLimitWindow,
) -> None:
    decision = await _hit(policy, scope, subject, window)
    if not decision.allowed:
        raise http_error_rate_limited(decision.retry_after_seconds)


async def _hit(
    policy: RateLimitPolicy,
    scope: str,
    subject: str,
    window: RateLimitWindow,
) -> RateLimitHit:
    if window.disabled:
        return RateLimitHit(allowed=True)
    client = await _redis(policy)
    if client is None:
        return RateLimitHit(allowed=True)
    key = _counter_key(policy, scope, subject)
    try:
        count = int(await client.incr(key))
        if count == 1:
            await client.expire(key, window.window_seconds)
        ttl = int(await client.ttl(key))
        if ttl < 0:
            await client.expire(key, window.window_seconds)
            ttl = window.window_seconds
    except RedisError:
        logger.warning("Rate-limit Redis increment failed", exc_info=True)
        if policy.fail_closed:
            raise http_error_rate_limit_unavailable() from None
        return RateLimitHit(allowed=True)
    if count > window.max_attempts:
        return RateLimitHit(allowed=False, retry_after_seconds=max(ttl, 1))
    return RateLimitHit(allowed=True, retry_after_seconds=max(ttl, 0))


async def _raise_if_locked(policy: RateLimitPolicy, scope: str, ident: str) -> None:
    if policy.login_lockout_seconds <= 0:
        return
    client = await _redis(policy)
    if client is None:
        return
    key = _lock_key(policy, scope, ident)
    try:
        if not await client.get(key):
            return
        ttl = int(await client.ttl(key))
    except RedisError:
        logger.warning("Rate-limit Redis lock read failed", exc_info=True)
        if policy.fail_closed:
            raise http_error_rate_limit_unavailable() from None
        return
    raise http_error_rate_limited(max(ttl, 1))


async def _set_lock(policy: RateLimitPolicy, scope: str, ident: str) -> None:
    seconds = policy.login_lockout_seconds
    if seconds <= 0:
        return
    client = await _redis(policy)
    if client is None:
        return
    try:
        await client.set(_lock_key(policy, scope, ident), "1", ex=seconds)
    except RedisError:
        logger.warning("Rate-limit Redis lock write failed", exc_info=True)


async def _delete_keys(policy: RateLimitPolicy, *keys: str) -> None:
    client = await _redis(policy)
    if client is None:
        return
    try:
        await client.delete(*keys)
    except RedisError:
        logger.warning("Rate-limit Redis delete failed", exc_info=True)


async def _redis(policy: RateLimitPolicy):
    if not policy.enabled:
        return None
    service = get_async_redis_service()
    if not service.is_configured:
        if policy.fail_closed:
            raise http_error_rate_limit_unavailable()
        logger.warning("Rate limit skipped: REDIS_URL is not configured")
        return None
    try:
        return service.get_client()
    except (RedisError, ValueError, RuntimeError):
        logger.warning("Rate-limit Redis client unavailable", exc_info=True)
        if policy.fail_closed:
            raise http_error_rate_limit_unavailable() from None
        return None


def _identity_key(value: str) -> str:
    normalized = value.strip().lower()
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:32]


def _counter_key(policy: RateLimitPolicy, scope: str, subject: str) -> str:
    return f"{policy.redis_prefix}:{scope}:{subject}"


def _lock_key(policy: RateLimitPolicy, scope: str, ident: str) -> str:
    return f"{policy.redis_prefix}:lock:{scope}:{ident}"