"""Schemi cambio password e cancellazione account (utente autenticato)."""

from __future__ import annotations

import re
from typing import Literal

from pydantic import BaseModel, Field, field_validator


def _validate_password_strength(v: str) -> str:
    if len(v) < 8:
        raise ValueError("Password must be at least 8 characters")
    if not re.search(r"\d", v):
        raise ValueError("Password must contain at least one number")
    if not re.search(r"[^A-Za-z0-9]", v):
        raise ValueError("Password must contain at least one special character")
    return v


class ChangePasswordRequest(BaseModel):
    """Cambio password da Settings.

    Se l'account ha già una password, ``current_password`` è obbligatoria.
    Se account solo OAuth (nessuna password), si può impostarne una nuova senza current.
    """

    current_password: str | None = Field(default=None, max_length=128)
    new_password: str = Field(min_length=8, max_length=128)

    @field_validator("current_password", mode="before")
    @classmethod
    def empty_current_to_none(cls, v: object) -> str | None:
        if v is None:
            return None
        if not isinstance(v, str):
            raise ValueError("Expected string or null")
        s = v.strip()
        return s if s else None

    @field_validator("new_password")
    @classmethod
    def validate_new_password(cls, v: str) -> str:
        return _validate_password_strength(v.strip())


class ChangePasswordResponse(BaseModel):
    status: str = "password_changed"


class DeactivateAccountRequest(BaseModel):
    """Conferma disattivazione account proprio.

    Se l'account ha password, ``password`` è obbligatoria.
    ``confirmation`` deve essere esattamente ``DISATTIVA``.
    """

    password: str | None = Field(default=None, max_length=128)
    confirmation: Literal["DISATTIVA"] = Field(
        description="Deve essere la stringa DISATTIVA per confermare.",
    )

    @field_validator("password", mode="before")
    @classmethod
    def empty_password_to_none(cls, v: object) -> str | None:
        if v is None:
            return None
        if not isinstance(v, str):
            raise ValueError("Expected string or null")
        s = v.strip()
        return s if s else None


class DeactivateAccountResponse(BaseModel):
    status: str = "deactivated"


class DeleteAccountRequest(BaseModel):
    """Conferma cancellazione account proprio.

    Se l'account ha password, ``password`` è obbligatoria.
    ``confirmation`` deve essere esattamente ``DELETE``.
    """

    password: str | None = Field(default=None, max_length=128)
    confirmation: Literal["DELETE"] = Field(
        description="Deve essere la stringa DELETE per confermare.",
    )

    @field_validator("password", mode="before")
    @classmethod
    def empty_password_to_none(cls, v: object) -> str | None:
        if v is None:
            return None
        if not isinstance(v, str):
            raise ValueError("Expected string or null")
        s = v.strip()
        return s if s else None


class DeleteAccountResponse(BaseModel):
    deleted: bool = True
