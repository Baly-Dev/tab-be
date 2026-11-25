"""Schemi API invitati iscrizione (growth)."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, Field

from services.storage import PublicMediaUrl


class SignupInviteeItem(BaseModel):
    """Profilo iscritto tramite il link invito del viewer."""

    id: uuid.UUID
    username: str
    first_name: str | None = None
    last_name: str | None = None
    avatar_url: PublicMediaUrl = None
    current_job_position: str | None = None
    current_company_name: str | None = None
    is_connector: bool = False
    signed_up_at: datetime = Field(description="``auth_users.created_at`` dell'invitato.")


class SignupInviteesListResponse(BaseModel):
    """Persone attribuite al link invito dell'utente autenticato."""

    items: list[SignupInviteeItem]
    total: int
    limit: int
    offset: int
