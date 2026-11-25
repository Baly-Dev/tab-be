"""Errori dominio e HTTP — inbox notifiche."""

from __future__ import annotations

from fastapi import HTTPException

from config.errors.http import http_exception_from_domain


class NotificationServiceError(Exception):
    """Errore business notifiche mappabile su risposta HTTP."""

    code: str = "notification_error"
    message: str = "Notification operation failed"
    http_status: int = 400

    def __init__(self, message: str | None = None) -> None:
        if message is not None:
            self.message = message
        super().__init__(self.message)


class NotificationNotFoundError(NotificationServiceError):
    """Notifica inesistente o non visibile al destinatario."""

    code = "notification_not_found"
    message = "Notification not found"
    http_status = 404


def http_error_from_notification(exc: NotificationServiceError) -> HTTPException:
    """Mappa eccezione notifiche su ``HTTPException``."""
    return http_exception_from_domain(exc)
