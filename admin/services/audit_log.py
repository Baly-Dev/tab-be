"""Scrittura e lettura del registro console (per modulo)."""

from __future__ import annotations

import logging
import uuid

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from admin.models.audit_log import AdminAuditLog
from admin.schemas.logs import AdminAuditLogItem, AdminAuditLogListResponse, AdminAuditModuleCount
from auth.models.user import AuthUser
from config.constants import AuditLevel, AuditModule

logger = logging.getLogger(__name__)


def record_audit(
    db: Session,
    *,
    module: AuditModule,
    action: str,
    message: str,
    actor: AuthUser | None = None,
    target_type: str | None = None,
    target_id: uuid.UUID | str | None = None,
    payload: dict | None = None,
    level: AuditLevel = AuditLevel.INFO,
) -> None:
    """Aggiunge una riga al registro. Non interrompe il flusso chiamante."""
    try:
        db.add(
            AdminAuditLog(
                module=module,
                action=action,
                level=level,
                actor_id=actor.id if actor is not None else None,
                actor_username=str(actor.username) if actor is not None else "sistema",
                target_type=target_type,
                target_id=str(target_id) if target_id is not None else None,
                message=message,
                payload=payload,
            )
        )
    except Exception:
        logger.exception("audit.write_failed action=%s module=%s", action, module.value)


def list_audit_logs(
    db: Session,
    *,
    module: AuditModule | None,
    action: str | None,
    level: AuditLevel | None,
    query: str | None,
    limit: int,
    offset: int,
) -> AdminAuditLogListResponse:
    """Elenco paginato, più conteggi per modulo."""
    filters = []
    if module is not None:
        filters.append(AdminAuditLog.module == module)
    if action:
        filters.append(AdminAuditLog.action == action.strip())
    if level is not None:
        filters.append(AdminAuditLog.level == level)
    if query:
        pattern = f"%{query.strip()}%"
        filters.append(
            or_(
                AdminAuditLog.message.ilike(pattern),
                AdminAuditLog.action.ilike(pattern),
                AdminAuditLog.actor_username.ilike(pattern),
                AdminAuditLog.target_id.ilike(pattern),
            )
        )

    stmt = select(AdminAuditLog)
    if filters:
        stmt = stmt.where(*filters)
    total = int(db.scalar(select(func.count()).select_from(stmt.order_by(None).subquery())) or 0)
    rows = list(
        db.scalars(stmt.order_by(AdminAuditLog.created_at.desc(), AdminAuditLog.id.desc()).limit(limit).offset(offset)).all()
    )

    count_rows = db.execute(
        select(AdminAuditLog.module, func.count()).group_by(AdminAuditLog.module)
    ).all()
    by_module = {getattr(row[0], "value", str(row[0])): int(row[1]) for row in count_rows}
    modules = [
        AdminAuditModuleCount(module=item.value, count=by_module.get(item.value, 0)) for item in AuditModule
    ]
    return AdminAuditLogListResponse(
        items=[_to_item(row) for row in rows],
        total=total,
        limit=limit,
        offset=offset,
        modules=modules,
    )


def _to_item(row: AdminAuditLog) -> AdminAuditLogItem:
    module = row.module if isinstance(row.module, AuditModule) else AuditModule(str(row.module))
    level = row.level if isinstance(row.level, AuditLevel) else AuditLevel(str(row.level))
    return AdminAuditLogItem(
        id=row.id,
        created_at=row.created_at,
        module=module.value,
        action=row.action,
        level=level.value,
        actor_id=row.actor_id,
        actor_username=row.actor_username,
        target_type=row.target_type,
        target_id=row.target_id,
        message=row.message,
        payload=row.payload if isinstance(row.payload, dict) else None,
    )
