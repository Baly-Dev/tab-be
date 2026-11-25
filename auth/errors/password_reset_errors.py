"""Errori HTTP — reset password."""

from __future__ import annotations

from fastapi import HTTPException, status


def http_error_password_reset_not_configured() -> HTTPException:
    """Reset password non configurato."""
    return HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail={
            "code": "password_reset_not_configured",
            "message": "Password reset is not configured",
        },
    )


def http_error_invalid_reset_token() -> HTTPException:
    """Token reset invalido o scaduto."""
    return HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail={"code": "invalid_reset_token", "message": "Invalid or expired reset token"},
    )


def http_error_account_cannot_reset_password() -> HTTPException:
    """Account non può reimpostare la password."""
    return HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail={
            "code": "account_cannot_reset_password",
            "message": "Account cannot reset password",
        },
    )


def http_error_reset_password_failed() -> HTTPException:
    """Errore generico durante reset password."""
    return HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail={"code": "reset_password_failed", "message": "Could not reset password"},
    )
