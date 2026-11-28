from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func

from config.db import Base


class AuthRefreshToken(Base):
    """Tabella `auth_refresh_tokens`: refresh JWT / logout revocabile (solo hash)."""

    __tablename__ = "auth_refresh_token"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("auth_users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    token_hash = Column(Text, unique=True, nullable=False)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    revoked_at = Column(DateTime(timezone=True), nullable=True)

    @property
    def is_revoked(self) -> bool:
        return self.revoked_at is not None

    def is_valid_at(self, when: datetime) -> bool:
        return not self.is_revoked and self.expires_at > when

    def revoke(self, when: datetime) -> None:
        if self.revoked_at is None:
            self.revoked_at = when