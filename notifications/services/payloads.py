"""Costruzione payload notifica (contratto JSONB condiviso web/native)."""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy.orm import Session

from auth.models.user import AuthUser
from core.models.profile import CoreProfile
from services.storage import public_asset_url


def snapshot_actor(db: Session, user_id: uuid.UUID) -> dict[str, Any]:
    """Dati attore al momento dell'evento (non join runtime in inbox)."""
    user = db.get(AuthUser, user_id)
    profile = db.get(CoreProfile, user_id)
    first_name = str(profile.first_name).strip() if profile is not None and profile.first_name else None
    last_name = str(profile.last_name).strip() if profile is not None and profile.last_name else None
    avatar = public_asset_url(profile.avatar_url) if profile is not None else None
    return {
        "actor_id": str(user_id),
        "actor_username": str(user.username) if user is not None else None,
        "actor_first_name": first_name or None,
        "actor_last_name": last_name or None,
        "actor_avatar_url": str(avatar).strip() if avatar else None,
    }


def connection_payload(
    *,
    connection_id: uuid.UUID,
    actor: dict[str, Any],
    deep_link: str,
) -> dict[str, Any]:
    """Payload per eventi rete (richiesta / accettazione)."""
    return {
        **actor,
        "entity_type": "connection",
        "entity_id": str(connection_id),
        "deep_link": deep_link,
    }
