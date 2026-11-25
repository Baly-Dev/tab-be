"""Errori dominio e HTTP — console admin."""

from __future__ import annotations

from fastapi import HTTPException, status

from config.errors.http import http_exception_from_domain


class AdminServiceError(Exception):
    """Errore business admin mappabile su risposta HTTP."""

    code: str = "admin_error"
    message: str = "Admin operation failed"
    http_status: int = 400

    def __init__(self, message: str | None = None) -> None:
        if message is not None:
            self.message = message
        super().__init__(self.message)


class AdminUserNotFoundError(AdminServiceError):
    """Utente assente in console."""

    code = "admin_user_not_found"
    message = "User not found"
    http_status = 404


class AdminConnectionNotFoundError(AdminServiceError):
    """Connessione assente in console."""

    code = "admin_connection_not_found"
    message = "Connection not found"
    http_status = 404


class AdminEventNotFoundError(AdminServiceError):
    """Evento assente in console."""

    code = "admin_event_not_found"
    message = "Event not found"
    http_status = 404


class AdminRsvpNotFoundError(AdminServiceError):
    """Iscrizione assente per l'evento."""

    code = "admin_rsvp_not_found"
    message = "Registration not found"
    http_status = 404


class AdminForbiddenMutationError(AdminServiceError):
    """Mutazione non consentita (es. ultimo super_admin, self-lockout)."""

    code = "admin_forbidden_mutation"
    message = "This change is not allowed"
    http_status = 409


class AdminInvalidRolesError(AdminServiceError):
    """Lista ruoli vuota o non valida."""

    code = "admin_invalid_roles"
    message = "At least one valid role is required"
    http_status = 422


class AdminBrevoNotConfiguredError(AdminServiceError):
    """Brevo non configurato o API Contacts non raggiungibile."""

    code = "brevo_not_configured"
    message = "Brevo non è configurato o i contatti non sono disponibili"
    http_status = 503


class InvalidTicketError(AdminServiceError):
    """Token assente o non riconosciuto."""

    code = "invalid_ticket"
    message = "Biglietto non riconosciuto"
    http_status = 404


class TicketNotEligibleError(AdminServiceError):
    """RSVP senza posto (waitlist / cancellato)."""

    code = "ticket_not_eligible"
    message = "Iscrizione non valida per l’ingresso"
    http_status = 409


class TicketWrongEventError(AdminServiceError):
    """Token valido ma per un altro evento."""

    code = "ticket_wrong_event"
    message = "Questo biglietto è di un altro evento"
    http_status = 409


class AdminBatchJobNotFoundError(AdminServiceError):
    """Job assente nel catalogo console."""

    code = "admin_batch_job_not_found"
    message = "Job non trovato"
    http_status = 404


class AdminBatchJobConfigError(AdminServiceError):
    """Configurazione job non valida."""

    code = "admin_batch_job_config"
    message = "Configurazione job non valida"
    http_status = 400


class TicketEventClosedError(AdminServiceError):
    """Evento in bozza o archiviato."""

    code = "ticket_event_closed"
    message = "Check-in non disponibile per questo evento"
    http_status = 409


def http_error_from_admin(exc: AdminServiceError) -> HTTPException:
    """Mapping errore dominio admin → HTTP."""
    return http_exception_from_domain(exc)


def http_error_admin_internal(message: str) -> HTTPException:
    """500 generico console."""
    return HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail={"code": "internal_error", "message": message},
    )
