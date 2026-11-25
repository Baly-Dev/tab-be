"""Signup request and response."""

import re
import uuid

from pydantic import BaseModel, Field, field_validator


class SignupRequest(BaseModel):
    """Email/password signup, or completion of a pending OAuth account."""

    email: str = Field(min_length=3, max_length=320)
    username: str = Field(min_length=3, max_length=32)
    password: str | None = Field(
        default=None,
        max_length=128,
        description=(
            "Required for email/password signup. "
            "Optional when finishing OAuth (POST /signup with Bearer, pending account)."
        ),
    )
    first_name: str = Field(min_length=1, max_length=200)
    last_name: str = Field(min_length=1, max_length=200)

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

    @field_validator("first_name", "last_name")
    @classmethod
    def strip_name(cls, v: str) -> str:
        s = v.strip()
        if not s:
            raise ValueError("Must not be empty")
        return s


class SignupResponse(BaseModel):
    id: uuid.UUID
    email: str
    username: str
    status: str
