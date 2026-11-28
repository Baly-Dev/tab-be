"""Venue: scheda locale. Galleria e menu stanno nelle tabelle collegate."""

from __future__ import annotations

import uuid
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    Numeric,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func

from config.constants import SubscriptionStatus, VenuePriceBand, VenueStaffRole, VenueStatus
from config.db import Base


class CoreVenue(Base):
    """Tabella ``core_venues``: identità pubblica del ristorante."""

    __tablename__ = "core_venues"
    __table_args__ = (UniqueConstraint("slug", name="uq_core_venues_slug"),)

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(Text, nullable=False)
    slug = Column(Text, nullable=False)
    summary = Column(Text, nullable=True)
    description = Column(Text, nullable=True)
    primary_cuisine = Column(Text, nullable=True)
    price_band = Column(
        Enum(
            VenuePriceBand,
            name="venue_price_band",
            values_callable=lambda obj: [m.value for m in obj],
        ),
        nullable=True,
    )
    phone = Column(Text, nullable=True)
    website = Column(Text, nullable=True)
    email = Column(Text, nullable=True)

    address_line = Column(Text, nullable=True)
    neighborhood = Column(Text, nullable=True)
    city = Column(Text, nullable=True)
    postal_code = Column(Text, nullable=True)
    country = Column(Text, nullable=True)
    latitude = Column(Numeric(9, 6), nullable=True)
    longitude = Column(Numeric(9, 6), nullable=True)
    timezone = Column(Text, nullable=False, server_default=text("'Europe/Rome'"))

    dress_code = Column(Text, nullable=True)
    cover_url = Column(Text, nullable=True)  # miniatura card; il carosello è ``core_venue_images``
    accepts_meal_vouchers = Column(
        Boolean,
        nullable=False,
        default=False,
        server_default=text("false"),
    )
    commission_rate = Column(Numeric(5, 4), nullable=False, default=Decimal("0.1500"), server_default=text("0.1500"))
    subscription_status = Column(
        Enum(
            SubscriptionStatus,
            name="subscription_status",
            values_callable=lambda obj: [m.value for m in obj],
        ),
        nullable=False,
        default=SubscriptionStatus.INACTIVE,
    )
    subscription_amount = Column(Numeric(10, 2), nullable=True)
    subscription_started_at = Column(DateTime(timezone=True), nullable=True)
    status = Column(
        Enum(
            VenueStatus,
            name="venue_status",
            values_callable=lambda obj: [m.value for m in obj],
        ),
        nullable=False,
        default=VenueStatus.DRAFT,
    )

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
    def is_published(self) -> bool:
        return self.status == VenueStatus.PUBLISHED

    @property
    def coordinates(self) -> tuple[Decimal, Decimal] | None:
        if self.latitude is None or self.longitude is None:
            return None
        return (self.latitude, self.longitude)

    def publish(self) -> None:
        self.status = VenueStatus.PUBLISHED

    def suspend(self) -> None:
        self.status = VenueStatus.SUSPENDED


class CoreVenueMembership(Base):
    """Operatore del venue. Lo stesso ``auth_users`` resta un professional."""

    __tablename__ = "core_venue_memberships"
    __table_args__ = (
        UniqueConstraint("venue_id", "user_id", name="uq_core_venue_memberships_venue_user"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    venue_id = Column(
        UUID(as_uuid=True),
        ForeignKey("core_venues.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("auth_users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    role = Column(
        Enum(
            VenueStaffRole,
            name="venue_staff_role",
            values_callable=lambda obj: [m.value for m in obj],
        ),
        nullable=False,
    )

    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    @property
    def can_manage_listing(self) -> bool:
        return self.role in {VenueStaffRole.OWNER, VenueStaffRole.MANAGER}

    @property
    def can_manage_bookings(self) -> bool:
        """Owner, manager e staff vedono e gestiscono il libro del locale."""
        return self.role in {VenueStaffRole.OWNER, VenueStaffRole.MANAGER, VenueStaffRole.STAFF}


class CoreVenueImage(Base):
    """Foto del locale. ``sort_order`` è l'ordine del carosello."""

    __tablename__ = "core_venue_images"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    venue_id = Column(
        UUID(as_uuid=True),
        ForeignKey("core_venues.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    url = Column(Text, nullable=False)
    caption = Column(Text, nullable=True)
    sort_order = Column(Integer, nullable=False, default=0, server_default=text("0"))

    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )