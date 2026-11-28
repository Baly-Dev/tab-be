from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, Text
from sqlalchemy.dialects.postgresql import ARRAY, BYTEA, UUID
from sqlalchemy.sql import func

from config.db import Base


class AuthWebAuthnCredential(Base):
    """Tabella ``auth_webauthn_credentials``: passkey / Face ID per utente."""

    __tablename__ = "auth_webauthn_credentials"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("auth_users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    credential_id = Column(BYTEA, unique=True, nullable=False)
    public_key = Column(BYTEA, nullable=False)
    sign_count = Column(Integer, nullable=False, default=0)
    transports = Column(ARRAY(Text), nullable=True)
    aaguid = Column(Text, nullable=True)
    device_name = Column(Text, nullable=False, default="Questo dispositivo")
    backed_up = Column(Boolean, nullable=False, default=False)
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    last_used_at = Column(DateTime(timezone=True), nullable=True)

    def record_use(self, when: datetime) -> None:
        self.last_used_at = when