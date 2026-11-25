"""Schemi reset password."""

import re

from pydantic import BaseModel, Field, field_validator

from auth.schemas.login import TokenResponse


class ForgotPasswordRequest(BaseModel):
    """Richiesta link reset (risposta sempre generica)."""

    email: str = Field(min_length=3, max_length=320)

    @field_validator("email")
    @classmethod
    def normalize_email(cls, v: str) -> str:
        s = v.strip().lower()
        if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", s):
            raise ValueError("Invalid email format")
        return s


class ForgotPasswordResponse(BaseModel):
    """Risposta anti-enumerazione."""

    status: str = "accepted"


class ResetPasswordRequest(BaseModel):
    """Imposta nuova password con token monouso dall'email."""

    token: str = Field(min_length=20, description="Token opaco dalla query ?token= del link.")
    password: str = Field(min_length=8, max_length=128)

    @field_validator("password")
    @classmethod
    def validate_password_strength(cls, v: str) -> str:
        if not re.search(r"\d", v):
            raise ValueError("Password must contain at least one number")
        if not re.search(r"[^A-Za-z0-9]", v):
            raise ValueError("Password must contain at least one special character")
        return v


class ResetPasswordResponse(TokenResponse):
    """Password aggiornata + auto-login (come verify-email)."""

    status: str = "password_reset"
