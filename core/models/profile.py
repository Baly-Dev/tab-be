from __future__ import annotations

from sqlalchemy import Boolean, Column, Date, DateTime, ForeignKey, Integer, SmallInteger, Text, text
from sqlalchemy.dialects.postgresql import ENUM, UUID
from sqlalchemy.sql import func

from config.constants import VenuePriceBand
from config.db import Base

_COMPLETENESS_FIELDS: tuple[str, ...] = (
    "first_name",
    "last_name",
    "bio",
    "avatar_url",
    "residence_country",
    "residence_city",
    "office_city",
    "office_neighborhood",
    "current_company_name",
    "current_job_position",
    "linkedin_url",
    "birth_date",
)

_PATCHABLE_FIELDS: frozenset[str] = frozenset(
    {
        "first_name",
        "last_name",
        "birth_date",
        "gender",
        "residence_country",
        "residence_city",
        "office_city",
        "office_neighborhood",
        "bio",
        "avatar_url",
        "current_company_name",
        "current_job_position",
        "linkedin_url",
        "marketing_consent",
        "preferred_cuisine",
        "preferred_price_band",
        "max_distance_meters",
        "dietary_notes",
        "prefers_meal_vouchers",
    }
)


class CoreProfile(Base):
    """Tabella `core_profiles`: dati profilo 1:1 con `auth_users` (`user_id` = PK + FK)."""

    __tablename__ = "core_profiles"

    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("auth_users.id", ondelete="CASCADE"),
        primary_key=True,
    )

    first_name = Column(Text, nullable=False)
    last_name = Column(Text, nullable=False)
    birth_date = Column(Date, nullable=True)
    gender = Column(Text, nullable=True)
    marketing_consent = Column(Boolean, nullable=False, default=False, server_default=text("false"))
    residence_country = Column(Text, nullable=True)
    residence_city = Column(Text, nullable=True)
    office_city = Column(Text, nullable=True)
    office_neighborhood = Column(Text, nullable=True)
    bio = Column(Text, nullable=True)
    avatar_url = Column(Text, nullable=True)

    current_company_name = Column(Text, nullable=True)
    current_job_position = Column(Text, nullable=True)
    linkedin_url = Column(Text, nullable=True)

    preferred_cuisine = Column(Text, nullable=True)
    preferred_price_band = Column(
        ENUM(
            VenuePriceBand,
            name="venue_price_band",
            create_type=False,
            values_callable=lambda obj: [m.value for m in obj],
        ),
        nullable=True,
    )
    max_distance_meters = Column(Integer, nullable=True)
    dietary_notes = Column(Text, nullable=True)
    prefers_meal_vouchers = Column(
        Boolean,
        nullable=False,
        default=False,
        server_default=text("false"),
    )

    profile_completeness = Column(
        SmallInteger,
        nullable=False,
        server_default=text("0"),
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
    def given_name(self) -> str:
        return str(self.first_name or "").strip()

    @property
    def full_name(self) -> str:
        parts = (self.given_name, str(self.last_name or "").strip())
        return " ".join(part for part in parts if part)

    @property
    def has_managed_avatar(self) -> bool:
        from services.storage import key_from_public_url

        return key_from_public_url(self.avatar_url) is not None

    def apply_patch(self, fields: dict[str, object]) -> None:
        """Aggiorna solo attributi profilo noti (ignora ``user_id``)."""
        for key, value in fields.items():
            if key in _PATCHABLE_FIELDS:
                setattr(self, key, value)

    def compute_completeness(self, *, has_interests: bool) -> int:
        """Stima 0–100 in base ai campi compilati (+ interessi)."""
        filled = sum(
            1 for field in _COMPLETENESS_FIELDS if self._field_is_filled(getattr(self, field, None))
        )
        if has_interests:
            filled += 1
        total = len(_COMPLETENESS_FIELDS) + 1
        return int(round(100 * filled / total))

    def refresh_completeness(self, *, has_interests: bool) -> None:
        """Ricalcola ``profile_completeness`` in memoria (senza commit)."""
        self.profile_completeness = self.compute_completeness(has_interests=has_interests)

    @staticmethod
    def _field_is_filled(value: object) -> bool:
        if value is None:
            return False
        if isinstance(value, str):
            return bool(value.strip())
        return True