"""Errori HTTP — rate limit e lockout."""

from __future__ import annotations

from fastapi import HTTPException, status


def http_error_rate_limited(retry_after_seconds: int = 0) -> HTTPException:
    """Troppi tentativi sulla stessa finestra."""
    retry_after = max(0, int(retry_after_seconds))
    headers = {"Retry-After": str(retry_after)} if retry_after > 0 else None
    return HTTPException(
        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        detail={
            "code": "rate_limited",
            "message": "Too many attempts. Try again later.",
            "retry_after": retry_after,
        },
        headers=headers,
    )


def http_error_rate_limit_unavailable() -> HTTPException:
    """Redis assente e ``RATE_LIMIT_FAIL_CLOSED`` attivo."""
    return HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail={
            "code": "rate_limit_unavailable",
            "message": "Rate limit store is unavailable",
        },
    )