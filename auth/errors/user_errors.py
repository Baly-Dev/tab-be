"""Errori HTTP — utente."""

from __future__ import annotations

from fastapi import HTTPException, status


def http_error_user_not_found() -> HTTPException:
    """Utente assente."""
    return HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail={"code": "user_not_found", "message": "User not found"},
    )
