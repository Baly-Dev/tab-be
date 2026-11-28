"""Prenotazione verso un venue e ordine sul menu. Il gruppo, se c'è, sta a parte."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Column,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    Text,
    text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func

from config.constants import BookingStatus, OrderStatus, PartyKind, PaymentMethod, PaymentStatus
from config.db import Base


class CoreBooking(Base):
    """Tavolo chiesto al locale. ``solo`` non ha un gruppo; ``group`` sì."""

    __tablename__ = "core_bookings"
    __table_args__ = (
        CheckConstraint("party_size >= 1", name="ck_core_bookings_party_size_positive"),
        Index("ix_core_bookings_venue_schedule", "venue_id", "scheduled_at"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    venue_id = Column(
        UUID(as_uuid=True),
        ForeignKey("core_venues.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    menu_id = Column(
        UUID(as_uuid=True),
        ForeignKey("core_venue_menus.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    host_user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("auth_users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    party_kind = Column(
        Enum(
            PartyKind,
            name="party_kind",
            values_callable=lambda obj: [m.value for m in obj],
        ),
        nullable=False,
    )
    status = Column(
        Enum(
            BookingStatus,
            name="booking_status",
            values_callable=lambda obj: [m.value for m in obj],
        ),
        nullable=False,
        default=BookingStatus.DRAFT,
    )
    scheduled_at = Column(DateTime(timezone=True), nullable=False)
    party_size = Column(Integer, nullable=False, default=1, server_default=text("1"))
    rsvp_deadline = Column(DateTime(timezone=True), nullable=True)
    note = Column(Text, nullable=True)
    venue_note = Column(Text, nullable=True)
    handled_by_user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("auth_users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    handled_at = Column(DateTime(timezone=True), nullable=True)

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
    def is_solo(self) -> bool:
        return self.party_kind == PartyKind.SOLO

    @property
    def is_group(self) -> bool:
        return self.party_kind == PartyKind.GROUP

    @property
    def is_open(self) -> bool:
        return self.status in {BookingStatus.DRAFT, BookingStatus.REQUESTED, BookingStatus.CONFIRMED}

    @property
    def is_visible_to_venue(self) -> bool:
        """Il locale non vede le bozze: solo ciò che l'ospite ha inviato o già chiuso."""
        return self.status != BookingStatus.DRAFT

    def request(self) -> None:
        self.status = BookingStatus.REQUESTED

    def confirm(self) -> None:
        self.status = BookingStatus.CONFIRMED

    def decline(self) -> None:
        self.status = BookingStatus.DECLINED

    def complete(self) -> None:
        self.status = BookingStatus.COMPLETED

    def cancel(self) -> None:
        self.status = BookingStatus.CANCELLED

    def mark_handled(self, staff_user_id: uuid.UUID, when: datetime) -> None:
        """Operatore del locale che ha confermato, rifiutato o chiuso la prenotazione."""
        self.handled_by_user_id = staff_user_id
        self.handled_at = when


class CoreOrder(Base):
    """Impegno di un professional su un menu, dentro una prenotazione.

    In solitaria c'è un ordine dell'host. In un gruppo lunch può essercene uno
    per il tavolo; in un'offerta flash uno per chi aderisce. La regola sta nella logica.
    """

    __tablename__ = "core_orders"
    __table_args__ = (
        CheckConstraint("covers >= 1", name="ck_core_orders_covers_positive"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    booking_id = Column(
        UUID(as_uuid=True),
        ForeignKey("core_bookings.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("auth_users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    menu_id = Column(
        UUID(as_uuid=True),
        ForeignKey("core_venue_menus.id", ondelete="SET NULL"),
        nullable=True,
    )
    covers = Column(Integer, nullable=False, default=1, server_default=text("1"))
    amount = Column(Numeric(10, 2), nullable=True)
    currency = Column(Text, nullable=False, default="EUR", server_default=text("'EUR'"))
    payment_method = Column(
        Enum(
            PaymentMethod,
            name="payment_method",
            values_callable=lambda obj: [m.value for m in obj],
        ),
        nullable=True,
    )
    payment_status = Column(
        Enum(
            PaymentStatus,
            name="payment_status",
            values_callable=lambda obj: [m.value for m in obj],
        ),
        nullable=False,
        default=PaymentStatus.UNPAID,
    )
    seat_committed = Column(Boolean, nullable=False, default=False, server_default=text("false"))
    commission_amount = Column(Numeric(10, 2), nullable=True)
    net_amount = Column(Numeric(10, 2), nullable=True)
    paid_at = Column(DateTime(timezone=True), nullable=True)
    status = Column(
        Enum(
            OrderStatus,
            name="order_status",
            values_callable=lambda obj: [m.value for m in obj],
        ),
        nullable=False,
        default=OrderStatus.DRAFT,
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

    def place(self) -> None:
        self.status = OrderStatus.PLACED

    def cancel(self) -> None:
        self.status = OrderStatus.CANCELLED

    def commit_seat(self) -> None:
        """Il posto conta sulla disponibilità del locale."""
        self.seat_committed = True

    def mark_paid(self, when: datetime) -> None:
        self.payment_status = PaymentStatus.PAID
        self.paid_at = when