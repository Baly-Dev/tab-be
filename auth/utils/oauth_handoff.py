"""One-time OAuth browser handoff. Tokens never travel in the redirect URL."""

from __future__ import annotations

import json
import re
import secrets
from typing import Any
from urllib.parse import urlencode, urlsplit, urlunsplit

from redis.exceptions import RedisError

from auth.errors.oauth_errors import OAuthHandoffUnavailableError
from services.redis import get_redis_service

_PREFIX = "auth:oauth_handoff"
_TTL_SECONDS = 60
_CODE_RE = re.compile(r"^[A-Za-z0-9_-]{32,128}$")


def issue_oauth_handoff(payload: dict[str, Any]) -> str:
    """Store the login payload and return a single-use code (60s)."""
    code = secrets.token_urlsafe(32)
    try:
        get_redis_service().get_client().set(
            f"{_PREFIX}:{code}",
            json.dumps(payload),
            ex=_TTL_SECONDS,
        )
    except (RedisError, ValueError) as exc:
        raise OAuthHandoffUnavailableError("Could not store OAuth handoff") from exc
    return code


def consume_oauth_handoff(code: str) -> dict[str, Any] | None:
    """Return the payload once. Missing, expired, reused, or malformed codes are None."""
    if not _CODE_RE.fullmatch(code):
        return None
    try:
        raw = get_redis_service().get_client().getdel(f"{_PREFIX}:{code}")
    except (RedisError, ValueError) as exc:
        raise OAuthHandoffUnavailableError("Could not read OAuth handoff") from exc
    if not raw:
        return None
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return None
    return data if isinstance(data, dict) else None


def handoff_redirect_url(frontend_base: str, code: str) -> str:
    """Put the code in the URL fragment so logs, proxies, and Referer never see it."""
    parts = urlsplit(frontend_base.strip())
    fragment = urlencode({"handoff": code})
    return urlunsplit((parts.scheme, parts.netloc, parts.path, parts.query, fragment))
