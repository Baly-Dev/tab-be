"""Overview KPI console admin."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from admin.errors import http_error_admin_internal
from admin.schemas.overview import AdminOverviewResponse
from admin.services.overview_service import load_admin_overview
from config.db.session import get_db
from core.dependencies import AdminReadUser

router = APIRouter()


@router.get("/overview", response_model=AdminOverviewResponse, summary="KPI dashboard admin")
def get_admin_overview(
    user: AdminReadUser,
    db: Session = Depends(get_db),
) -> AdminOverviewResponse:
    """Contatori utenti, rete ed eventi. Lettura: admin e super_admin."""
    try:
        return load_admin_overview(db, user)
    except SQLAlchemyError as exc:
        raise http_error_admin_internal("Unable to load admin overview") from exc
