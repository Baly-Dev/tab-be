"""Schemi login, refresh e logout."""

import uuid

from pydantic import BaseModel, Field


class LoginRequest(BaseModel):
    """Email o username + password."""

    identifier: str = Field(min_length=3, max_length=320)
    password: str = Field(min_length=1, max_length=128)


class AuthUserBrief(BaseModel):
    id: uuid.UUID
    email: str
    username: str
    status: str


class TokenResponse(BaseModel):
    """Risposta standard per login e refresh (FE: Bearer access + cookie/body refresh)."""

    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int = Field(description="Secondi di validità dell'access token.")
    user: AuthUserBrief


class RefreshRequest(BaseModel):
    refresh_token: str = Field(min_length=20)


class LogoutRequest(BaseModel):
    """Solo il refresh da revocare; l'identità viene dall'header Bearer (access_token)."""

    refresh_token: str = Field(
        min_length=20,
        description="refresh_token dalla risposta login (non l'access_token).",
    )


class LogoutResponse(BaseModel):
    status: str = "logged_out"


def normalize_login_identifier(value: str) -> str:
    return value.strip().lower()
