import uuid

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, Text, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func

from config.db import Base


class CoreInterest(Base):
    """Tabella ``core_interests``: singolo topic; opzionalmente legato a una categoria."""

    __tablename__ = "core_interests"
    __table_args__ = (UniqueConstraint("slug", name="uq_core_interests_slug"),)

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    category_id = Column(
        UUID(as_uuid=True),
        ForeignKey("core_interest_categories.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    name = Column(Text, nullable=False)
    slug = Column(Text, nullable=False)
    description = Column(Text, nullable=True)
    is_active = Column(Boolean, nullable=False, server_default=text("true"))  # soft delete
    sort_order = Column(Integer, nullable=False, server_default=text("0"))

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
    def is_selectable(self) -> bool:
        return bool(self.is_active)