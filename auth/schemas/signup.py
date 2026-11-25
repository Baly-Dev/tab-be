"""Pydantic schemi per signup."""

import re
import uuid
from datetime import date
from typing import Self

from pydantic import BaseModel, Field, field_validator, model_validator

from config.constants import Gender
from core.utils.age import require_adult_birth_date
from services.storage import PublicMediaUrl

_OPTIONAL_PROFILE_STR_FIELDS = (
    "residence_country",
    "residence_city",
    "bio",
    "avatar_url",
    "current_company_name",
    "current_job_position",
    "linkedin_url",
)


class SignupRequest(BaseModel):
    """Payload finale wizard: credenziali, profilo completo (colonne core_profiles), interessi."""

    email: str = Field(min_length=3, max_length=320)
    username: str = Field(min_length=3, max_length=32)
    password: str | None = Field(
        default=None,
        max_length=128,
        description=(
            "Obbligatoria per signup email/password. "
            "Opzionale se completamento OAuth (POST /signup con Bearer, account pending)."
        ),
    )
    first_name: str = Field(min_length=1, max_length=200)
    last_name: str = Field(min_length=1, max_length=200)

    birth_date: date
    gender: Gender
    marketing_consent: bool = False
    residence_country: str | None = Field(default=None, max_length=200)
    residence_city: str | None = Field(default=None, max_length=200)
    bio: str | None = Field(default=None, max_length=2000)
    avatar_url: PublicMediaUrl = Field(default=None, max_length=2000)
    current_company_name: str | None = Field(default=None, max_length=300)
    current_job_position: str | None = Field(default=None, max_length=300)
    linkedin_url: str | None = Field(default=None, max_length=2000)

    interest_ids: list[uuid.UUID] = Field(
        default_factory=list,
        max_length=64,
        description="Interessi opzionali (core_interests.id attivi); duplicati ignorati.",
    )
    inviter_referral_code: str | None = Field(
        default=None,
        max_length=64,
        description="Codice invito `?ref=` opzionale; solo connector, admin e super_admin.",
    )

    @field_validator("email")
    @classmethod
    def normalize_email(cls, v: str) -> str:
        s = v.strip().lower()
        if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", s):
            raise ValueError("Invalid email format")
        return s

    @field_validator("username")
    @classmethod
    def normalize_username(cls, v: str) -> str:
        s = v.strip().lower()
        if not re.fullmatch(r"[a-z0-9_]{3,32}", s):
            raise ValueError(
                "Username must be 3–32 characters: lowercase letters, digits, underscore only"
            )
        return s

    @field_validator("password", mode="before")
    @classmethod
    def empty_password_to_none(cls, v: object) -> str | None:
        if v is None:
            return None
        if not isinstance(v, str):
            raise ValueError("Expected string or null")
        s = v.strip()
        return s if s else None

    @field_validator("password")
    @classmethod
    def validate_password_strength(cls, v: str | None) -> str | None:
        if v is None:
            return None
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters")
        if not re.search(r"\d", v):
            raise ValueError("Password must contain at least one number")
        if not re.search(r"[^A-Za-z0-9]", v):
            raise ValueError("Password must contain at least one special character")
        return v

    @field_validator("birth_date")
    @classmethod
    def validate_adult_birth_date(cls, value: date) -> date:
        return require_adult_birth_date(value)

    @field_validator("first_name", "last_name")
    @classmethod
    def strip_name(cls, v: str) -> str:
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

    @field_validator("inviter_referral_code", mode="before")
    @classmethod
    def empty_inviter_code_to_none(cls, v: object) -> str | None:
        if v is None:
            return None
        if isinstance(v, str) and not v.strip():
            return None
        if not isinstance(v, str):
            raise ValueError("Expected string or null")
        return v.strip()

    @model_validator(mode="after")
    def dedupe_interest_ids(self) -> Self:
        self.interest_ids = list(dict.fromkeys(self.interest_ids))
        return self


class SignupResponse(BaseModel):
    id: uuid.UUID
    email: str
    username: str
    status: str
