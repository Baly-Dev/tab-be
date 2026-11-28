"""Schemi richiesta PATCH /core/me."""

from __future__ import annotations

import uuid
from datetime import date
from typing import Self

from pydantic import BaseModel, Field, field_validator, model_validator

from core.utils.age import require_adult_birth_date
from services.storage import PublicMediaUrl

_OPTIONAL_PROFILE_STR_FIELDS = (
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
    "preferred_cuisine",
    "dietary_notes",
)


class UpdateMeRequest(BaseModel):
    """Aggiornamento parziale del profilo proprio (e interessi opzionali).

    Solo i campi presenti nel body vengono applicati (``exclude_unset``).
    ``interest_ids`` se inviato sostituisce l'intero set (lista vuota = nessun interesse).
    """

    first_name: str | None = Field(default=None, min_length=1, max_length=200)
    last_name: str | None = Field(default=None, min_length=1, max_length=200)
    birth_date: date | None = None
    gender: str | None = Field(default=None, max_length=100)
    residence_country: str | None = Field(default=None, max_length=200)
    residence_city: str | None = Field(default=None, max_length=200)
    office_city: str | None = Field(default=None, max_length=200)
    office_neighborhood: str | None = Field(default=None, max_length=200)
    bio: str | None = Field(default=None, max_length=2000)
    avatar_url: PublicMediaUrl = Field(default=None, max_length=2000)
    current_company_name: str | None = Field(default=None, max_length=300)
    current_job_position: str | None = Field(default=None, max_length=300)
    linkedin_url: str | None = Field(default=None, max_length=2000)
    preferred_cuisine: str | None = Field(default=None, max_length=200)
    preferred_price_band: str | None = Field(default=None, max_length=8)
    max_distance_meters: int | None = Field(default=None, ge=0, le=50_000)
    dietary_notes: str | None = Field(default=None, max_length=500)
    prefers_meal_vouchers: bool | None = None
    interest_ids: list[uuid.UUID] | None = Field(
        default=None,
        max_length=64,
        description="Se presente, sostituisce gli interessi (lista vuota ammessa).",
    )

    @field_validator("birth_date")
    @classmethod
    def validate_adult_birth_date(cls, value: date | None) -> date | None:
        if value is None:
            return None
        return require_adult_birth_date(value)

    @field_validator("first_name", "last_name")
    @classmethod
    def strip_required_name(cls, v: str | None) -> str | None:
        if v is None:
            return None
        s = v.strip()
        if not s:
            raise ValueError("Must not be empty")
        return s

    @field_validator(*_OPTIONAL_PROFILE_STR_FIELDS, mode="before")
    @classmethod
    def optional_profile_str_strip(cls, v: object) -> str | None:
        if v is None:
            return None
        if not isinstance(v, str):
            raise ValueError("Expected string or null")
        s = v.strip()
        return s if s else None

    @model_validator(mode="after")
    def dedupe_interest_ids(self) -> Self:
        if self.interest_ids is not None:
            self.interest_ids = list(dict.fromkeys(self.interest_ids))
        return self
