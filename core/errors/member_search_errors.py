"""Errori dominio e HTTP — ricerca membri."""

from __future__ import annotations

from fastapi import HTTPException, status


class MemberSearchServiceError(Exception):
    """Errore business ricerca membri mappabile su risposta HTTP."""

    code: str = "member_search_error"
    message: str = "Member search failed"
    http_status: int = 400

    def __init__(self, message: str | None = None) -> None:
        if message is not None:
            self.message = message
        super().__init__(self.message)


class InvalidSearchQueryError(MemberSearchServiceError):
    """Query di ricerca non valida o troppo corta."""

    code = "invalid_search_query"
    message = "Search query is invalid"
    http_status = 422


class SearchNotAllowedError(MemberSearchServiceError):
    """Viewer non autorizzato a cercare membri."""

    code = "search_not_allowed"
    message = "You are not allowed to search members"
    http_status = 403


def http_error_from_member_search(exc: MemberSearchServiceError) -> HTTPException:
    """Mappa eccezione ricerca su ``HTTPException``."""
    return HTTPException(
        status_code=exc.http_status,
        detail={"code": exc.code, "message": exc.message},
    )
