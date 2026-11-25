"""Errori HTTP — cambio password / cancellazione account."""

from __future__ import annotations

from fastapi import HTTPException, status


def http_error_wrong_current_password() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail={
            "code": "wrong_current_password",
            "message": "Current password is incorrect",
        },
    )


def http_error_current_password_required() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        detail={
            "code": "current_password_required",
            "message": "Current password is required",
        },
    )


def http_error_password_required_for_delete() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        detail={
            "code": "password_required",
            "message": "Password is required to delete this account",
        },
    )


def http_error_wrong_password_for_delete() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail={
            "code": "wrong_password",
            "message": "Password is incorrect",
        },
    )


def http_error_last_super_admin() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail={
            "code": "last_super_admin",
            "message": "Cannot close the last super admin account",
        },
    )


def http_error_deactivate_account_failed() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail={
            "code": "deactivate_account_failed",
            "message": "Could not deactivate account",
        },
    )


def http_error_delete_account_failed() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail={
            "code": "delete_account_failed",
            "message": "Could not delete account",
        },
    )


def http_error_change_password_failed() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail={
            "code": "change_password_failed",
            "message": "Could not change password",
        },
    )


def http_error_social_account_not_linked() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail={
            "code": "social_account_not_linked",
            "message": "This provider is not linked to your account",
        },
    )


def http_error_cannot_unlink_last_login() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail={
            "code": "cannot_unlink_last_login",
            "message": "Set a password or link another provider before disconnecting this account",
        },
    )


def http_error_unlink_social_account_failed() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail={
            "code": "unlink_social_account_failed",
            "message": "Could not disconnect the linked account",
        },
    )
