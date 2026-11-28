"""Azienda (organization): entità distinta dal professional che ci lavora."""

from __future__ import annotations

import uuid

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func

from config.db import Base


class CoreOrganization(Base):
    """Tabella ``core_organizations``: ragione sociale / studio / coworking."""

    __tablename__ = "core_organizations"
    __table_args__ = (UniqueConstraint("slug", name="uq_core_organizations_slug"),)

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(Text, nullable=False)
    slug = Column(Text, nullable=False)
    logo_url = Column(Text, nullable=True)
    website = Column(Text, nullable=True)
    industry = Column(Text, nullable=True)
    city = Column(Text, nullable=True)
    country = Column(Text, nullable=True)

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


class CoreOrganizationAffiliation(Base):
    """Un professional lavora in un'organization (titolo, affiliazione corrente)."""

    __tablename__ = "core_organization_affiliations"
    __table_args__ = (
        UniqueConstraint(
            "organization_id",
            "user_id",
            name="uq_core_organization_affiliations_org_user",
        ),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id = Column(
        UUID(as_uuid=True),
        ForeignKey("core_organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("auth_users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    title = Column(Text, nullable=True)
    is_current = Column(Boolean, nullable=False, default=True, server_default="true")

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

    def mark_current(self) -> None:
        self.is_current = True

    def mark_past(self) -> None:
        self.is_current = False