import uuid

from sqlalchemy import Column, DateTime, Enum, Text
from sqlalchemy.dialects.postgresql import CITEXT, UUID
from sqlalchemy.sql import func

from config.constants import UserStatus
from config.db import Base


class AuthUser(Base):
    """Table ``auth_users``: credentials, login identifiers, account status."""

    __tablename__ = "auth_users"

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
    first_name = Column(Text, nullable=False)
    last_name = Column(Text, nullable=False)

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
