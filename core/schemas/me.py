"""Schemi risposta GET /core/me."""

from __future__ import annotations

import uuid
from datetime import date, datetime

from pydantic import BaseModel, Field

from services.storage import PublicMediaUrl


class MeInterestItem(BaseModel):
    """Interesse scelto dall'utente."""

    id: uuid.UUID
    name: str


class LinkedAccountItem(BaseModel):
    """Account OAuth collegato (login con Google / LinkedIn)."""

    provider: str
    email: str | None = None


class MeConnectionsSummary(BaseModel):
    """Conteggi connessioni 1° grado (per badge / sezione rete in profilo)."""

    accepted: int = 0
    pending: int = 0
    blocked: int = 0


class MeProfileResponse(BaseModel):
    """Dati ``core_profiles`` (1:1 con utente)."""

    first_name: str
    last_name: str
    birth_date: date | None = None
    gender: str | None = None
    marketing_consent: bool = False
    residence_country: str | None = None
    residence_city: str | None = None
    bio: str | None = None
    avatar_url: PublicMediaUrl = None
    current_company_name: str | None = None
    current_job_position: str | None = None
    linkedin_url: str | None = None
    profile_completeness: int = 0
    created_at: datetime
    updated_at: datetime


class MeResponse(BaseModel):
    """Utente autenticato + profilo + stato registrazione (per guard FE e dashboard)."""

    id: uuid.UUID
    email: str
    username: str
    status: str = Field(description="pending | active | suspended | deleted")
    referral_code: str
    invites_count: int = Field(
        default=0,
        description="Utenti iscritti tramite il link invito di questo account.",
    )
    has_password: bool = Field(description="False se account senza password (solo OAuth/passkey).")
    has_passkeys: bool = Field(
        default=False,
        description="True se è registrata almeno una passkey / Face ID.",
    )
    email_verified_at: datetime | None = None
    registration_complete: bool = Field(
        description="True se l'account è active e ha un profilo (interessi non obbligatori).",
    )
    roles: list[str]
    linked_providers: list[str] = Field(
        default_factory=list,
        description="Provider OAuth collegati (es. google, linkedin).",
    )
    linked_accounts: list[LinkedAccountItem] = Field(
        default_factory=list,
        description="Account OAuth collegati con email del provider.",
    )
    connections: MeConnectionsSummary = Field(default_factory=MeConnectionsSummary)
    interests: list[MeInterestItem]
    profile: MeProfileResponse | None = None
    created_at: datetime
    updated_at: datetime
