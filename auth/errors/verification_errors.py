"""Errori HTTP — verifica email."""

from __future__ import annotations

from fastapi import HTTPException, status


def http_error_verification_not_configured() -> HTTPException:
    """JWT verification non configurato."""
    return HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail={
            "code": "verification_not_configured",
            "message": "Email verification is not configured",
        },
    )


def http_error_verification_link_expired() -> HTTPException:
    """Token verifica email scaduto."""
    return HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail={"code": "verification_link_expired", "message": "Verification link expired"},
    )


def http_error_invalid_verification_token() -> HTTPException:
    """Token verifica email invalido."""
    return HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail={"code": "invalid_verification_token", "message": "Invalid verification token"},
    )


def http_error_verification_token_mismatch() -> HTTPException:
    """Token non corrisponde all'account."""
    return HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail={
            "code": "verification_token_mismatch",
            "message": "Token does not match this account",
        },
    )
