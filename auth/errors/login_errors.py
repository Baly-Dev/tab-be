"""Errori HTTP — login, refresh e logout."""

from __future__ import annotations

from fastapi import HTTPException, status


def http_error_invalid_credentials() -> HTTPException:
    """Email/username o password errati."""
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail={"code": "invalid_credentials", "message": "Invalid credentials"},
    )


def http_error_email_not_verified() -> HTTPException:
    """Account in attesa verifica email."""
    return HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail={"code": "email_not_verified", "message": "Email not verified"},
    )


def http_error_account_suspended() -> HTTPException:
    """Account sospeso."""
    return HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail={"code": "account_suspended", "message": "Account suspended"},
    )


def http_error_account_deleted() -> HTTPException:
    """Account eliminato."""
    return HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail={"code": "account_deleted", "message": "Account deleted"},
    )


def http_error_account_inactive() -> HTTPException:
    """Account non attivo (generico login/refresh)."""
    return HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail={"code": "account_inactive", "message": "Account inactive"},
    )


def http_error_auth_not_configured() -> HTTPException:
    """JWT_SECRET o store refresh non configurati."""
    return HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail={"code": "auth_not_configured", "message": "Auth is not configured"},
    )


def http_error_invalid_refresh_token() -> HTTPException:
    """Refresh token assente, scaduto o revocato."""
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail={"code": "invalid_refresh_token", "message": "Invalid or expired refresh token"},
    )


def http_error_logout_wrong_token_type() -> HTTPException:
    """Access JWT inviato nel body logout al posto del refresh opaco."""
    return HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail={
            "code": "wrong_token_type",
            "message": "Body must be the opaque refresh_token from login, not the JWT access_token.",
        },
    )


def http_error_refresh_token_forbidden() -> HTTPException:
    """Refresh token di un altro utente."""
    return HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail={
            "code": "forbidden",
            "message": "Refresh token does not belong to this account",
        },
    )
