import uuid

from sqlalchemy import Column, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func

from config.db import Base


class CoreUserInterest(Base):
    """Tabella ``core_user_interests``: interessi scelti dall'utente (es. signup)."""

    __tablename__ = "core_user_interests"
    __table_args__ = (
        UniqueConstraint("user_id", "interest_id", name="uq_core_user_interests_user_interest"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("auth_users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    interest_id = Column(
        UUID(as_uuid=True),
        ForeignKey("core_interests.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
