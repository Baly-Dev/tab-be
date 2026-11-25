import secrets
import string
import uuid

from sqlalchemy import CheckConstraint, Column, DateTime, Enum, ForeignKey, Text
from sqlalchemy.dialects.postgresql import CITEXT, UUID
from sqlalchemy.sql import func

from config.constants import UserStatus
from config.db import Base


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
