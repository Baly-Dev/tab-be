from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func

from config.db import Base


class AuthPasswordResetToken(Base):
    """Token monouso per reset password (solo hash in DB)."""

    __tablename__ = "auth_password_reset_token"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("auth_users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    token_hash = Column(Text, unique=True, nullable=False, index=True)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    used_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    @property
    def is_used(self) -> bool:
        return self.used_at is not None

    def is_valid_at(self, when: datetime) -> bool:
        return not self.is_used and self.expires_at > when

    def mark_used(self, when: datetime) -> None:
        if self.used_at is None:
            self.used_at = when