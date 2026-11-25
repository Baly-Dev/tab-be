"""Errori dominio e HTTP — OAuth social."""

from __future__ import annotations

from fastapi import HTTPException, status


class OAuthSignInError(Exception):
    """Errore generico flusso OAuth social."""


class OAuthNotConfiguredError(OAuthSignInError):
    """Provider OAuth non configurato o JWT_SECRET assente."""


class OAuthStateError(OAuthSignInError):
    """State assente, scaduto o non valido."""

    def __init__(self, message: str = "Invalid or expired OAuth state") -> None:
        self.message = message
        super().__init__(message)


class OAuthExchangeError(OAuthSignInError):
    """Scambio code/token o userinfo fallito."""

    def __init__(self, message: str = "OAuth sign-in failed") -> None:
        self.message = message
        super().__init__(message)


class OAuthProfileError(OAuthSignInError):
    """Profilo provider incompleto o email non verificata."""

    def __init__(self, message: str = "OAuth profile error") -> None:
        self.message = message
        super().__init__(message)


class OAuthAccountError(OAuthSignInError):
    """Account non utilizzabile (sospeso, eliminato, conflitto)."""

    def __init__(self, message: str = "Account cannot sign in with OAuth") -> None:
        self.message = message
        super().__init__(message)


def http_error_from_oauth(exc: OAuthSignInError, *, provider_label: str) -> HTTPException:
    """Mappa eccezione OAuth su ``HTTPException`` con ``code`` strutturato."""
    if isinstance(exc, OAuthNotConfiguredError):
        return HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "code": "oauth_not_configured",
                "message": f"{provider_label} OAuth is not configured",
            },
        )
    if isinstance(exc, OAuthStateError):
        return HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "code": "invalid_oauth_state",
                "message": exc.message or "Invalid OAuth state",
            },
        )
    if isinstance(exc, OAuthExchangeError):
        return HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "code": "oauth_exchange_failed",
                "message": exc.message or f"{provider_label} sign-in failed",
            },
        )
    if isinstance(exc, OAuthProfileError):
        return HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "code": "oauth_profile_error",
                "message": exc.message or f"{provider_label} sign-in failed",
            },
        )
    if isinstance(exc, OAuthAccountError):
        return HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "code": "oauth_account_error",
                "message": exc.message or f"Account cannot sign in with {provider_label}",
            },
        )
    return HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail={"code": "oauth_sign_in_failed", "message": f"{provider_label} sign-in failed"},
    )
