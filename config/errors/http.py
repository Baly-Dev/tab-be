"""Mapping eccezioni dominio → ``HTTPException`` (pattern condiviso)."""

from __future__ import annotations

from typing import Protocol

from fastapi import HTTPException


class DomainHttpError(Protocol):
    """Contratto minimo per errori mappabili su risposta API strutturata."""

    code: str
    message: str
    http_status: int


def http_exception_from_domain(exc: DomainHttpError) -> HTTPException:
    """Converte un errore dominio con ``code`` / ``message`` / ``http_status``."""
    return HTTPException(
        status_code=exc.http_status,
        detail={"code": exc.code, "message": exc.message},
    )
