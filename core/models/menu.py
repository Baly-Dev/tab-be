"""Menu del venue: una o più carte, ciascuna con una o più immagini."""

from __future__ import annotations

import uuid

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    Numeric,
    SmallInteger,
    Text,
    Time,
    text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func

from config.constants import VenueMenuKind
from config.db import Base


class CoreVenueMenu(Base):
    """Carta pubblicata dal locale (pranzo, cena, flash, altro)."""

    __tablename__ = "core_venue_menus"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    venue_id = Column(
        UUID(as_uuid=True),
        ForeignKey("core_venues.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name = Column(Text, nullable=False)
    description = Column(Text, nullable=True)
    includes = Column(Text, nullable=True)
    price_amount = Column(Numeric(10, 2), nullable=True)
    compare_at_price = Column(Numeric(10, 2), nullable=True)
    currency = Column(Text, nullable=False, default="EUR", server_default=text("'EUR'"))
    covers_limit = Column(Integer, nullable=True)
    offer_starts_at = Column(DateTime(timezone=True), nullable=True)
    offer_ends_at = Column(DateTime(timezone=True), nullable=True)
    kind = Column(
        Enum(
            VenueMenuKind,
            name="venue_menu_kind",
            values_callable=lambda obj: [m.value for m in obj],
        ),
        nullable=False,
        default=VenueMenuKind.LUNCH,
    )
    sort_order = Column(Integer, nullable=False, default=0, server_default=text("0"))
    is_published = Column(Boolean, nullable=False, default=False, server_default=text("false"))

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

    def publish(self) -> None:
        self.is_published = True

    def unpublish(self) -> None:
        self.is_published = False

    @property
    def is_flash(self) -> bool:
        return self.kind == VenueMenuKind.FLASH


class CoreVenueMenuWindow(Base):
    """Fascia in cui il locale rende prenotabile questa carta. La aggiorna il ristorante."""

    __tablename__ = "core_venue_menu_windows"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    menu_id = Column(
        UUID(as_uuid=True),
        ForeignKey("core_venue_menus.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    weekday = Column(SmallInteger, nullable=False)
    starts_at = Column(Time, nullable=False)
    ends_at = Column(Time, nullable=False)


class CoreVenueMenuImage(Base):
    """Immagine di un menu. ``sort_order`` è l'ordine nel carosello della carta."""

    __tablename__ = "core_venue_menu_images"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    menu_id = Column(
        UUID(as_uuid=True),
        ForeignKey("core_venue_menus.id", ondelete="CASCADE"),
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