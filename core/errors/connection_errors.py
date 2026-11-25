"""Errori dominio e HTTP — connessioni utente."""

from __future__ import annotations

from fastapi import HTTPException

from config.errors.http import http_exception_from_domain


class ConnectionServiceError(Exception):
    """Errore business connessioni mappabile su risposta HTTP."""

    code: str = "connection_error"
    message: str = "Connection operation failed"
    http_status: int = 400

    def __init__(self, message: str | None = None) -> None:
        if message is not None:
            self.message = message
        super().__init__(self.message)


class TargetUserNotFoundError(ConnectionServiceError):
    """Utente target assente o non connettibile."""

    code = "target_user_not_found"
    message = "Target user not found or not available"
    http_status = 404


class CannotConnectToSelfError(ConnectionServiceError):
    """Auto-connessione non consentita."""

    code = "cannot_connect_to_self"
    message = "You cannot connect to yourself"
    http_status = 400


class ConnectionNotFoundError(ConnectionServiceError):
    """Connessione inesistente o non visibile al viewer."""

    code = "connection_not_found"
    message = "Connection not found"
    http_status = 404


class ConnectionBlockedError(ConnectionServiceError):
    """Relazione bloccata tra i due utenti."""

    code = "connection_blocked"
    message = "Connection is blocked"
    http_status = 403


class AlreadyConnectedError(ConnectionServiceError):
    """Connessione già accettata."""

    code = "already_connected"
    message = "Users are already connected"
    http_status = 409


class ConnectionAlreadyPendingError(ConnectionServiceError):
    """Richiesta già inviata dal viewer."""

    code = "connection_already_pending"
    message = "Connection request is already pending"
    http_status = 409


class InvalidConnectionActionError(ConnectionServiceError):
    """Azione non consentita nello stato corrente."""

    code = "invalid_connection_action"
    message = "This action is not allowed for the current connection state"
    http_status = 422


class EventAlertNotAllowedError(ConnectionServiceError):
    """Avviso iscrizione consentito solo con connessione accepted."""

    code = "event_alert_not_allowed"
    message = "Event alerts require an accepted connection"
    http_status = 403


def http_error_from_connection(exc: ConnectionServiceError) -> HTTPException:
    """Mappa eccezione connessioni su ``HTTPException``."""
    return http_exception_from_domain(exc)
