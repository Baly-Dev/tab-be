import uuid

from sqlalchemy import Column, DateTime, Integer, Text, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func

from config.db import Base


class CoreInterestCategory(Base):
    """Tabella ``core_interest_categories``: macro-area per argomenti / topic (signup, discovery)."""

    __tablename__ = "core_interest_categories"
    __table_args__ = (UniqueConstraint("slug", name="uq_core_interest_categories_slug"),)

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(Text, nullable=False, unique=True)
    slug = Column(Text, nullable=False)
    description = Column(Text, nullable=True)
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
