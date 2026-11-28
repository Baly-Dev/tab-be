"""Coperti del locale. Il ristorante li pubblica; l'utente li consulta prima di prenotare.

I posti già impegnati non stanno qui: si ricavano dalle prenotazioni confermate.
"""

from __future__ import annotations

import uuid

from sqlalchemy import Boolean, Column, Date, ForeignKey, Integer, SmallInteger, Time, text
from sqlalchemy.dialects.postgresql import UUID

from config.db import Base


class CoreVenueShift(Base):
    """Turno ricorrente (es. pranzo lunedì–venerdì) e coperti di quel turno."""

    __tablename__ = "core_venue_shifts"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    venue_id = Column(
        UUID(as_uuid=True),
        ForeignKey("core_venues.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    weekday = Column(SmallInteger, nullable=False)
    starts_at = Column(Time, nullable=False)
    ends_at = Column(Time, nullable=False)
    covers_total = Column(Integer, nullable=False)


class CoreVenueShiftOverride(Base):
    """Eccezione di un giorno: coperti diversi oppure locale chiuso."""

    __tablename__ = "core_venue_shift_overrides"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    venue_id = Column(
        UUID(as_uuid=True),
        ForeignKey("core_venues.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    service_date = Column(Date, nullable=False, index=True)
    starts_at = Column(Time, nullable=False)
    ends_at = Column(Time, nullable=False)
    covers_total = Column(Integer, nullable=True)
    is_closed = Column(Boolean, nullable=False, default=False, server_default=text("false"))