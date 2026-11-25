"""Tabella ``notifications``: inbox in-app per utente."""

from __future__ import annotations

import uuid

from sqlalchemy import Boolean, Column, DateTime, Enum, ForeignKey, Index, Text, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.sql import func

from config.constants import NotificationType
from config.db import Base


class Notification(Base):
    """Riga inbox: tipo + payload strutturato, indipendente dai canali email/push."""

    __tablename__ = "notifications"
    __table_args__ = (
        Index("ix_notifications_inbox", "user_id", "read", "created_at"),
        Index(
            "uq_notifications_user_type_dedup",
            "user_id",
            "type",
            "dedup_key",
            unique=True,
            postgresql_where=text("dedup_key IS NOT NULL"),
        ),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("auth_users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    type = Column(
        Enum(
            NotificationType,
            name="notification_type",
            values_callable=lambda obj: [m.value for m in obj],
        ),
        nullable=False,
    )
    payload = Column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))
    read = Column(Boolean, nullable=False, default=False, server_default=text("false"))
    read_at = Column(DateTime(timezone=True), nullable=True)
    dedup_key = Column(Text, nullable=True)
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
