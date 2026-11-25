"""Schemi WebAuthn / passkey."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class PasskeyAuthenticateOptionsRequest(BaseModel):
    """Identifier opzionale per restringere le credenziali; vuoto = passkey discoverable."""

    identifier: str | None = Field(default=None, max_length=320)


class PasskeyOptionsResponse(BaseModel):
    """Options WebAuthn + JWT con la challenge (da rinviare in verify)."""

    options: dict[str, Any]
    challenge_token: str


class PasskeyRegisterRequest(BaseModel):
    challenge_token: str = Field(min_length=20)
    credential: dict[str, Any]
    device_name: str | None = Field(default=None, max_length=80)


class PasskeyAuthenticateRequest(BaseModel):
    challenge_token: str = Field(min_length=20)
    credential: dict[str, Any]


class PasskeyItem(BaseModel):
    id: uuid.UUID
    device_name: str
    created_at: datetime
    last_used_at: datetime | None = None
    backed_up: bool = False


class PasskeyListResponse(BaseModel):
    items: list[PasskeyItem]


class PasskeyDeleteResponse(BaseModel):
    deleted: bool = True
