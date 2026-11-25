"""Errori HTTP — upload immagini (avatar, cover)."""

from __future__ import annotations

from fastapi import HTTPException, status


def http_error_invalid_image() -> HTTPException:
    """422 — file assente, formato non supportato o immagine illeggibile."""
    return HTTPException(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        detail={
            "code": "invalid_image",
            "message": "Upload a valid JPG, PNG or WebP image",
        },
    )


def http_error_image_too_large(*, max_mb: int) -> HTTPException:
    """413 — file oltre il limite."""
    return HTTPException(
        status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
        detail={
            "code": "image_too_large",
            "message": f"Image must be at most {max_mb} MB",
        },
    )


def http_error_storage_unavailable() -> HTTPException:
    """503 — backend storage non raggiungibile."""
    return HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail={
            "code": "storage_unavailable",
            "message": "Unable to store the image right now",
        },
    )
