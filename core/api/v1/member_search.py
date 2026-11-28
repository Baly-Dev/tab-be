"""Ricerca membri (search bar / autocomplete)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from auth.utils.helpers import AuthenticatedUser
from config.db import get_async_db
from core.errors.member_search_errors import (
    MemberSearchServiceError,
    http_error_from_member_search,
)
from core.schemas.member_search import MemberSearchResponse
from core.services.member_search_service import search_members

router = APIRouter()


@router.get(
    "",
    response_model=MemberSearchResponse,
    summary="Cerca membri",
)
async def get_member_search(
    user: AuthenticatedUser,
    db: AsyncSession = Depends(get_async_db),
    q: str = Query(
        min_length=1,
        max_length=64,
        description="Nome, cognome, username o nome completo (min 2 caratteri effettivi).",
    ),
    limit: int = Query(default=20, ge=1, le=50),
    offset: int = Query(default=0, ge=0),
) -> MemberSearchResponse:
    """Ricerca leggera di membri attivi visibili al viewer autenticato."""
    try:
        return await search_members(db, user, query=q, limit=limit, offset=offset)
    except MemberSearchServiceError as exc:
        raise http_error_from_member_search(exc) from exc
    except SQLAlchemyError as exc:
        raise HTTPException(
            status_code=500,
            detail={"code": "internal_error", "message": "Unable to search members"},
        ) from exc
