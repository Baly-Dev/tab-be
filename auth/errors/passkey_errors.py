"""Errori HTTP — passkey / WebAuthn."""

from __future__ import annotations

from fastapi import HTTPException, status


def http_error_webauthn_not_configured() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail={"code": "webauthn_not_configured", "message": "Passkeys are not configured"},
    )


def http_error_invalid_passkey_challenge() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail={
            "code": "invalid_passkey_challenge",
            "message": "Passkey challenge is invalid or expired",
        },
    )


def http_error_passkey_registration_failed() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail={"code": "passkey_registration_failed", "message": "Could not register passkey"},
    )


def http_error_passkey_already_registered() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail={
            "code": "passkey_already_registered",
            "message": "This passkey is already registered",
        },
    )


def http_error_passkey_not_found() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail={"code": "passkey_not_found", "message": "Passkey not found"},
    )


def http_error_cannot_delete_last_login() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail={
            "code": "cannot_unlink_last_login",
            "message": "Set a password or link another sign-in method before removing this passkey",
        },
    )
