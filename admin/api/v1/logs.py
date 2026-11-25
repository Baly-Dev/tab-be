"""Registro strutturato — solo super_admin."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, Query
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from admin.errors import http_error_admin_internal
from admin.schemas.logs import AdminAuditLogListResponse
from admin.services.audit_log import list_audit_logs
from config.constants import AuditLevel, AuditModule
from config.db.session import get_db
from core.dependencies import AdminLogsUser

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("", response_model=AdminAuditLogListResponse, summary="Registro per modulo")
def get_admin_logs(
    _actor: AdminLogsUser,
    db: Session = Depends(get_db),
    module: AuditModule | None = Query(default=None),
    action: str | None = Query(default=None, max_length=80),
    level: AuditLevel | None = Query(default=None),
    q: str | None = Query(default=None, max_length=80),
    limit: int = Query(default=40, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> AdminAuditLogListResponse:
    """Elenco consultabile. Visibile solo al super_admin."""
    try:
        return list_audit_logs(
            db,
            module=module,
            action=action,
            level=level,
            query=q,
            limit=limit,
            offset=offset,
        )
    except SQLAlchemyError as exc:
        logger.exception("admin.logs.list_failed")
        raise http_error_admin_internal("Unable to load audit logs") from exc
