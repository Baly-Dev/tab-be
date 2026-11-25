"""Errori HTTP — sessione JWT / Bearer."""

from __future__ import annotations

from fastapi import HTTPException, status


def _bearer_headers() -> dict[str, str]:
    return {"WWW-Authenticate": "Bearer"}


def http_error_wrong_token_type() -> HTTPException:
    """Refresh token usato al posto dell'access token in Authorization."""
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail={
            "code": "wrong_token_type",
            "message": (
                "Use access_token (JWT) in Authorization, not refresh_token. "
                "refresh_token goes in the logout body only."
            ),
        },
        headers=_bearer_headers(),
    )


def http_error_access_token_expired() -> HTTPException:
    """Access token JWT scaduto."""
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail={"code": "access_token_expired", "message": "Access token expired"},
        headers=_bearer_headers(),
    )


def http_error_invalid_access_token() -> HTTPException:
    """Access token JWT invalido."""
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail={"code": "invalid_access_token", "message": "Invalid access token"},
        headers=_bearer_headers(),
    )


def http_error_invalid_access_token_payload() -> HTTPException:
    """Payload JWT access privo di ``sub`` valido."""
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail={"code": "invalid_access_token", "message": "Invalid access token"},
        headers=_bearer_headers(),
    )


def http_error_bearer_user_not_found() -> HTTPException:
    """Utente del JWT non trovato in DB."""
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail={"code": "user_not_found", "message": "User not found"},
        headers=_bearer_headers(),
    )


def http_error_account_not_active() -> HTTPException:
    """Account sospeso, eliminato o non attivo."""
    return HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail={"code": "account_inactive", "message": "Account is not active"},
    )


def http_error_not_authenticated(*, docs_hint: bool = False) -> HTTPException:
    """Bearer assente o non valido."""
    message = (
        "Click Authorize in /docs and paste access_token (JWT from login). "
        "Do not use the refresh_token in Authorization."
        if docs_hint
        else "Authorization Bearer access_token required"
    )
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail={"code": "not_authenticated", "message": message},
        headers=_bearer_headers(),
    )
