"""Modello ``admin_audit_logs`` — registro strutturato per la console super admin."""

from __future__ import annotations

import uuid

from sqlalchemy import Column, DateTime, Enum, ForeignKey, Index, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID

from config.constants import AuditLevel, AuditModule
from config.db import Base

_ENUM_VALUES = lambda obj: [m.value for m in obj]


class AdminAuditLog(Base):
    """Riga di log di dominio, consultabile per modulo."""

    __tablename__ = "admin_audit_logs"
    __table_args__ = (
        Index("ix_admin_audit_logs_module_created_at", "module", "created_at"),
        Index("ix_admin_audit_logs_created_at", "created_at"),
        Index("ix_admin_audit_logs_action", "action"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    module = Column(
        Enum(AuditModule, name="audit_module", values_callable=_ENUM_VALUES),
        nullable=False,
    )
    action = Column(Text, nullable=False)
    level = Column(
        Enum(AuditLevel, name="audit_level", values_callable=_ENUM_VALUES),
        nullable=False,
        default=AuditLevel.INFO,
    )
    actor_id = Column(
        UUID(as_uuid=True),
        ForeignKey("auth_users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    actor_username = Column(Text, nullable=True)
    target_type = Column(Text, nullable=True)
    target_id = Column(Text, nullable=True)
    message = Column(Text, nullable=False)
    payload = Column(JSONB, nullable=True)
