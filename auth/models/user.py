from __future__ import annotations

import secrets
import string
import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, Column, DateTime, Enum, ForeignKey, Text
from sqlalchemy.dialects.postgresql import CITEXT, UUID
from sqlalchemy.sql import func

from config.constants import UserStatus
from config.db import Base

if TYPE_CHECKING:
    from core.models.profile import CoreProfile


def _default_referral_code() -> str:
    """Codice stabile per link invito iscrizione (`?ref=`); collisione rara → retry in app."""
    alphabet = string.ascii_uppercase + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(10))


class AuthUser(Base):
    """Tabella `auth_users`: credenziali, identificativi login, growth inviti, stato account."""

    __tablename__ = "auth_users"

    __table_args__ = (
        CheckConstraint(
            "invited_by_id IS NULL OR invited_by_id <> id",
            name="ck_auth_users_invited_by_not_self",
        ),
    )

    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    # CREATE EXTENSION IF NOT EXISTS citext;
    email = Column(
        CITEXT,
        unique=True,
        nullable=False,
        index=True,
    )
    username = Column(
        CITEXT,
        unique=True,
        nullable=False,
        index=True,
    )

    referral_code = Column(
        Text,
        nullable=False,
        unique=True,
        index=True,
        default=_default_referral_code,
    )
    invited_by_id = Column(
        UUID(as_uuid=True),
        ForeignKey("auth_users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    password_hash = Column(Text, nullable=True)

    status = Column(
        Enum(UserStatus, name="user_status"),
        nullable=False,
    )

    email_verified_at = Column(DateTime(timezone=True), nullable=True)

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

    @property
    def has_password(self) -> bool:
        return self.password_hash is not None

    @property
    def is_email_verified(self) -> bool:
        return self.email_verified_at is not None

    def is_oauth_pending(self) -> bool:
        """Utente creato/collegato via OAuth, wizard non ancora completato."""
        return self.status == UserStatus.PENDING and self.password_hash is None

    def is_email_password_pending(self) -> bool:
        """Signup classico in attesa di verifica email."""
        return self.status == UserStatus.PENDING and self.password_hash is not None

    def pending_signup_reason(self) -> str | None:
        """Motivo dello ``status=pending`` (verifica email vs onboarding OAuth)."""
        if self.status != UserStatus.PENDING:
            return None
        if self.is_email_password_pending():
            return "email_verification"
        if self.is_oauth_pending():
            return "oauth_onboarding"
        return "incomplete"

    def is_registration_complete(self, profile: CoreProfile | None) -> bool:
        """True se l'account è operativo (``active`` + profilo; interessi opzionali)."""
        return self.status == UserStatus.ACTIVE and profile is not None

    def mark_email_verified_from_provider(self, *, email_verified: bool) -> None:
        """Segna email verificata dal provider OAuth; ACTIVE solo dopo POST /signup."""
        if email_verified and self.email_verified_at is None:
            self.email_verified_at = datetime.now(tz=UTC)

    def verify_password(self, plain: str) -> bool:
        """Verifica password in chiaro contro ``password_hash`` (bcrypt / legacy WP)."""
        if self.password_hash is None:
            return False
        from auth.utils.passwords import verify_password

        return verify_password(plain, str(self.password_hash))