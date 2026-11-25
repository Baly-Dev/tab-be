"""Schemi verifica email."""

import re

from pydantic import BaseModel, Field, field_validator

from auth.schemas.login import TokenResponse


class VerifyEmailRequest(BaseModel):
    token: str = Field(min_length=20, description="JWT dalla query FE o dal link.")


class VerifyEmailResponse(TokenResponse):
    """Come login/refresh + ``status`` (verified | already_verified) per auto-login post-verifica."""

    status: str = Field(description="verified | already_verified")


class ResendVerificationRequest(BaseModel):
    email: str = Field(min_length=3, max_length=320)

    @field_validator("email")
    @classmethod
    def normalize_email(cls, v: str) -> str:
        s = v.strip().lower()
        if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", s):
            raise ValueError("Invalid email format")
        return s


class ResendVerificationResponse(BaseModel):
    """Risposta generica (anti-enumerazione account)."""

    status: str
