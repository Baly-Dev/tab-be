from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import Column, DateTime, Enum, ForeignKey, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import CITEXT, JSONB, UUID
from sqlalchemy.sql import func

from config.constants import OAuthProvider
from config.db import Base


class AuthSocialAccount(Base):
    """Tabella `auth_social_accounts`: link OAuth per utente (provider + id remoto)."""

    __tablename__ = "auth_social_accounts"
    __table_args__ = (
        UniqueConstraint("provider", "provider_user_id", name="uq_auth_social_accounts_provider_remote"),
        UniqueConstraint("user_id", "provider", name="uq_auth_social_accounts_user_provider"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("auth_users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    provider = Column(
        Enum(
            OAuthProvider,
            name="oauth_provider",
            values_callable=lambda obj: [m.value for m in obj],
        ),
        nullable=False,
    )
    provider_user_id = Column(Text, nullable=False)
    email = Column(CITEXT, nullable=True)
    raw_profile = Column(JSONB, nullable=True)
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    def sync_provider_profile(
        self,
        *,
        email: str | None,
        raw_profile: dict[str, Any] | None,
    ) -> None:
        """Aggiorna snapshot email e payload grezzo dal provider."""
        self.email = email
        self.raw_profile = raw_profile