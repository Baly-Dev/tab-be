"""Errori HTTP — signup e completamento wizard."""

from __future__ import annotations

from fastapi import HTTPException, status


def http_error_invalid_interest_ids() -> HTTPException:
    """Interessi inesistenti o disattivati."""
    return HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail={
            "code": "invalid_interest_ids",
            "message": "One or more interest ids are invalid or inactive",
        },
    )


def http_error_unknown_referral_code() -> HTTPException:
    """Codice invito non riconosciuto."""
    return HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail={"code": "unknown_referral_code", "message": "Unknown inviter referral code"},
    )


def http_error_signup_token_mismatch() -> HTTPException:
    """Bearer non corrisponde all'utente in completamento OAuth."""
    return HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail={"code": "token_mismatch", "message": "Token does not match signup email"},
    )


def http_error_signup_not_allowed() -> HTTPException:
    """Account non completabile via signup."""
    return HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail={
            "code": "signup_not_allowed",
            "message": "Account cannot be completed via signup",
        },
    )


def http_error_registration_already_complete() -> HTTPException:
    """Wizard già completato."""
    return HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail={
            "code": "registration_complete",
            "message": "Registration already completed",
        },
    )


def http_error_username_taken() -> HTTPException:
    """Username già in uso."""
    return HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail={"code": "username_taken", "message": "Username already taken"},
    )


def http_error_email_or_username_taken() -> HTTPException:
    """Email o username già registrati."""
    return HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail={
            "code": "email_or_username_taken",
            "message": "Email or username already registered",
        },
    )


def http_error_email_verification_pending() -> HTTPException:
    """Signup email/password in attesa verifica."""
    return HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail={
            "code": "email_verification_pending",
            "message": "Check your email to verify your account before signing in",
        },
    )


def http_error_account_cannot_register() -> HTTPException:
    """Stato account non registrabile."""
    return HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail={"code": "account_cannot_register", "message": "Account cannot be registered"},
    )


def http_error_password_required() -> HTTPException:
    """Password obbligatoria per signup email."""
    return HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail={"code": "password_required", "message": "Password is required for email signup"},
    )
