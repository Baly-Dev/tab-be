import time
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from starlette.requests import Request

from auth.utils.rate_limit import (
    allow_password_reset_email,
    clear_login_identifier_limits,
    client_ip,
    enforce_ip_limit,
    enforce_login_limits,
    enforce_signup_limits,
    reject_if_api_limited,
    should_limit_api_path,
)
from config.rate_limit import RateLimitPolicy
from config.settings import Settings


class _FakeRedis:
    def __init__(self) -> None:
        self.store: dict[str, tuple[str, float | None]] = {}

    def _purge(self, key: str) -> None:
        item = self.store.get(key)
        if item is None:
            return
        _, expires_at = item
        if expires_at is not None and expires_at <= time.time():
            self.store.pop(key, None)

    async def incr(self, key: str) -> int:
        self._purge(key)
        value, expires_at = self.store.get(key, ("0", None))
        count = int(value) + 1
        self.store[key] = (str(count), expires_at)
        return count

    async def expire(self, key: str, seconds: int) -> bool:
        self._purge(key)
        if key not in self.store:
            return False
        value, _ = self.store[key]
        self.store[key] = (value, time.time() + seconds)
        return True

    async def ttl(self, key: str) -> int:
        self._purge(key)
        item = self.store.get(key)
        if item is None:
            return -2
        _, expires_at = item
        if expires_at is None:
            return -1
        return max(0, int(expires_at - time.time()))

    async def get(self, key: str) -> str | None:
        self._purge(key)
        item = self.store.get(key)
        return None if item is None else item[0]

    async def set(self, key: str, value: str, ex: int | None = None) -> bool:
        expires_at = None if ex is None else time.time() + ex
        self.store[key] = (str(value), expires_at)
        return True

    async def delete(self, *keys: str) -> int:
        removed = 0
        for key in keys:
            if self.store.pop(key, None) is not None:
                removed += 1
        return removed


class _RedisService:
    def __init__(self, client: _FakeRedis, *, configured: bool = True) -> None:
        self._client = client
        self.is_configured = configured

    def get_client(self) -> _FakeRedis:
        return self._client


def _request(*, ip: str = "203.0.113.10", forwarded: str | None = None) -> Request:
    headers: list[tuple[bytes, bytes]] = []
    if forwarded:
        headers.append((b"x-forwarded-for", forwarded.encode("utf-8")))
    return Request(
        {
            "type": "http",
            "asgi": {"version": "3.0"},
            "http_version": "1.1",
            "method": "POST",
            "scheme": "http",
            "path": "/api/v1/auth/login",
            "raw_path": b"/api/v1/auth/login",
            "query_string": b"",
            "headers": headers,
            "client": (ip, 4321),
            "server": ("test", 80),
        }
    )


def _settings(**overrides) -> Settings:
    values = {
        "rate_limit_enabled": True,
        "rate_limit_fail_closed": False,
        "rate_limit_trust_x_forwarded_for": False,
        "rate_limit_login_ip_max_attempts": 20,
        "rate_limit_login_identifier_max_attempts": 3,
        "rate_limit_login_lockout_seconds": 60,
        "rate_limit_signup_ip_max_attempts": 20,
        "rate_limit_signup_email_max_attempts": 2,
        "rate_limit_password_reset_email_max_attempts": 2,
        "rate_limit_api_ip_max_attempts": 2,
        "jwt_secret": "test-secret",
        "redis_url": "redis://localhost:6380/0",
    }
    values.update(overrides)
    return Settings(**values)


def _install(monkeypatch, settings: Settings, redis: _RedisService) -> None:
    monkeypatch.setattr("auth.utils.rate_limit.get_settings", lambda: settings)
    monkeypatch.setattr("auth.utils.rate_limit.get_async_redis_service", lambda: redis)


def test_settings_expose_structured_rate_limit_policy() -> None:
    settings = _settings()
    policy = settings.rate_limit
    assert isinstance(policy, RateLimitPolicy)
    assert policy.login_identifier.max_attempts == 3
    assert policy.password_reset_email.max_attempts == 2
    assert policy.redis_prefix == "tn:rl"


async def test_login_identifier_is_rate_limited_then_locked(monkeypatch) -> None:
    settings = _settings()
    redis = _RedisService(_FakeRedis())
    _install(monkeypatch, settings, redis)
    request = _request()

    await enforce_login_limits(request, "ada@example.com")
    await enforce_login_limits(request, "ada@example.com")
    await enforce_login_limits(request, "ada@example.com")
    with pytest.raises(HTTPException) as exc:
        await enforce_login_limits(request, "ada@example.com")
    assert exc.value.status_code == 429
    assert exc.value.detail["code"] == "rate_limited"
    assert "Retry-After" in (exc.value.headers or {})

    with pytest.raises(HTTPException) as locked:
        await enforce_login_limits(request, "ada@example.com")
    assert locked.value.status_code == 429


async def test_successful_login_clears_identifier_limit(monkeypatch) -> None:
    settings = _settings()
    redis = _RedisService(_FakeRedis())
    _install(monkeypatch, settings, redis)
    request = _request()
    for _ in range(3):
        await enforce_login_limits(request, "ada@example.com")
    await clear_login_identifier_limits("ada@example.com")
    await enforce_login_limits(request, "ada@example.com")


async def test_signup_email_limit_returns_429(monkeypatch) -> None:
    settings = _settings()
    redis = _RedisService(_FakeRedis())
    _install(monkeypatch, settings, redis)
    request = _request()
    await enforce_signup_limits(request, "ada@example.com")
    await enforce_signup_limits(request, "ada@example.com")
    with pytest.raises(HTTPException) as exc:
        await enforce_signup_limits(request, "ada@example.com")
    assert exc.value.status_code == 429


async def test_password_reset_email_limit_is_silent(monkeypatch) -> None:
    settings = _settings()
    redis = _RedisService(_FakeRedis())
    _install(monkeypatch, settings, redis)
    assert await allow_password_reset_email("ada@example.com") is True
    assert await allow_password_reset_email("ada@example.com") is True
    assert await allow_password_reset_email("ada@example.com") is False


async def test_zero_max_attempts_disables_the_bucket(monkeypatch) -> None:
    settings = _settings(rate_limit_login_identifier_max_attempts=0)
    redis = _RedisService(_FakeRedis())
    _install(monkeypatch, settings, redis)
    request = _request()
    for _ in range(12):
        await enforce_login_limits(request, "ada@example.com")


def test_client_ip_uses_forwarded_header_only_when_trusted() -> None:
    request = _request(ip="10.0.0.8", forwarded="198.51.100.20, 10.0.0.1")
    trusted = SimpleNamespace(
        rate_limit=SimpleNamespace(trust_x_forwarded_for=True),
    )
    untrusted = SimpleNamespace(
        rate_limit=SimpleNamespace(trust_x_forwarded_for=False),
    )
    assert client_ip(request, policy=trusted.rate_limit) == "198.51.100.20"
    assert client_ip(request, policy=untrusted.rate_limit) == "10.0.0.8"


async def test_fail_closed_without_redis_returns_503(monkeypatch) -> None:
    settings = _settings(rate_limit_fail_closed=True)
    redis = _RedisService(_FakeRedis(), configured=False)
    _install(monkeypatch, settings, redis)
    with pytest.raises(HTTPException) as exc:
        await enforce_ip_limit(_request(), "api")
    assert exc.value.status_code == 503
    assert exc.value.detail["code"] == "rate_limit_unavailable"


async def test_global_api_limiter_returns_json_429(monkeypatch) -> None:
    settings = _settings()
    redis = _RedisService(_FakeRedis())
    _install(monkeypatch, settings, redis)
    request = _request()
    assert await reject_if_api_limited(request) is None
    assert await reject_if_api_limited(request) is None
    blocked = await reject_if_api_limited(request)
    assert blocked is not None
    assert blocked.status_code == 429


def test_health_and_docs_are_not_globally_limited() -> None:
    assert should_limit_api_path("/health") is False
    assert should_limit_api_path("/docs") is False
    assert should_limit_api_path("/api/v1/auth/login") is True