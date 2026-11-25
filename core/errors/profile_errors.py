"""Errori HTTP — profilo pubblico / aggiornamento me."""

from __future__ import annotations

from fastapi import HTTPException, status


def http_error_for_profile_not_found() -> HTTPException:
    """404 uniforme per profilo non trovato o non accessibile."""
    return HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail={
            "code": "profile_not_found",
            "message": "User profile not found or not available",
        },
    )


def http_error_for_own_profile_missing() -> HTTPException:
    """404 quando l'utente autenticato non ha ancora una riga ``core_profiles``."""
    return HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail={
            "code": "own_profile_missing",
            "message": "Your profile record was not found",
        },
    )


def http_error_invalid_interest_ids() -> HTTPException:
    """422 — uno o più interest_ids non validi / inattivi."""
    return HTTPException(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        detail={
            "code": "invalid_interest_ids",
            "message": "One or more interest ids are invalid or inactive",
        },
    )


def http_error_for_profile_connections_forbidden() -> HTTPException:
    """403 — serve una connessione accepted per vedere la rete del profilo."""
    return HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail={
            "code": "profile_connections_forbidden",
            "message": "You must be connected to view this user's connections",
        },
    )


def http_error_empty_update() -> HTTPException:
    """422 — body PATCH senza campi da aggiornare."""
    return HTTPException(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        detail={
            "code": "empty_update",
            "message": "At least one field is required",
        },
    )
