"""Copia nel bucket le foto profilo arrivate da LinkedIn o Google."""

from __future__ import annotations

import logging
import uuid
from urllib.parse import urlparse

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.models.profile import CoreProfile
from core.models.user_interest import CoreUserInterest
from services.images import process_avatar
from services.storage import get_storage_service, key_from_public_url

logger = logging.getLogger(__name__)

MAX_PROVIDER_AVATAR_BYTES = 5 * 1024 * 1024
_FETCH_TIMEOUT_SECONDS = 15.0


def is_managed_avatar_url(url: str | None) -> bool:
    """True se l'URL è già un oggetto nostro servito da ``GET /media/``."""
    return key_from_public_url(url) is not None


def provider_picture_allowed(url: str | None) -> bool:
    """True solo per HTTPS su CDN LinkedIn o Google (niente URL arbitrari)."""
    raw = (url or "").strip()
    if urlparse(raw).scheme != "https":
        return False
    return _allowed_host(_hostname(raw))


async def apply_provider_avatar(db: AsyncSession, profile: CoreProfile, picture_url: str | None) -> bool:
    """Sostituisce un avatar esterno con la copia nel bucket.

    Non tocca una foto già salvata sotto ``/media/``. Se il download fallisce
    lascia ``avatar_url`` invariato e restituisce False.
    """
    raw = (picture_url or "").strip()
    if not raw or profile.has_managed_avatar:
        return False
    stored = mirror_remote_avatar(profile.user_id, raw)
    if not stored:
        return False
    profile.avatar_url = stored
    has_interests = (
        await db.scalar(
            select(CoreUserInterest.interest_id)
            .where(CoreUserInterest.user_id == profile.user_id)
            .limit(1)
        )
        is not None
    )
    profile.refresh_completeness(has_interests=has_interests)
    db.add(profile)
    return True


def mirror_remote_avatar(user_id: uuid.UUID, picture_url: str) -> str | None:
    """Scarica, normalizza in WebP e salva. ``None`` se l'URL non è usabile."""
    data = fetch_remote_image(picture_url)
    if data is None:
        return None
    try:
        processed = process_avatar(data)
    except Exception:
        logger.warning(
            "provider_avatar.invalid_image user_id=%s host=%s",
            user_id,
            _hostname(picture_url),
        )
        return None
    key = f"avatars/{user_id}/{uuid.uuid4()}.webp"
    try:
        return get_storage_service().put_bytes(key, processed, "image/webp")
    except Exception:
        logger.warning(
            "provider_avatar.store_failed user_id=%s host=%s",
            user_id,
            _hostname(picture_url),
        )
        return None


def fetch_remote_image(url: str) -> bytes | None:
    """GET dell'immagine. Rifiuta host non consentiti, anche dopo un redirect."""
    if not provider_picture_allowed(url):
        logger.warning("provider_avatar.host_rejected host=%s", _hostname(url))
        return None
    try:
        with httpx.Client(timeout=_FETCH_TIMEOUT_SECONDS, follow_redirects=True) as client:
            response = client.get(url)
    except httpx.HTTPError:
        logger.warning("provider_avatar.fetch_failed host=%s", _hostname(url))
        return None
    final_host = _hostname(str(response.url))
    if not _allowed_host(final_host):
        logger.warning("provider_avatar.redirect_rejected host=%s", final_host)
        return None
    if response.status_code != 200:
        logger.warning(
            "provider_avatar.fetch_status host=%s status=%s",
            final_host,
            response.status_code,
        )
        return None
    data = response.content
    if not data or len(data) > MAX_PROVIDER_AVATAR_BYTES:
        logger.warning("provider_avatar.bad_size host=%s", final_host)
        return None
    content_type = (response.headers.get("content-type") or "").split(";", 1)[0].strip().lower()
    if content_type and not content_type.startswith("image/"):
        logger.warning("provider_avatar.bad_type host=%s type=%s", final_host, content_type)
        return None
    return data


def _hostname(url: str | None) -> str:
    raw = (url or "").strip()
    if not raw:
        return ""
    return (urlparse(raw).hostname or "").lower().rstrip(".")


def _allowed_host(host: str) -> bool:
    if not host or host in {"localhost", "127.0.0.1", "::1"}:
        return False
    return (
        host == "licdn.com"
        or host.endswith(".licdn.com")
        or host.endswith(".googleusercontent.com")
        or host.endswith(".ggpht.com")
    )
