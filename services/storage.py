"""Object storage: disco locale (dev) o S3-compatible (Railway Bucket privato)."""

from __future__ import annotations

import logging
import os
import shutil
from functools import lru_cache
from pathlib import Path
from typing import Annotated

from pydantic import BeforeValidator

from config import get_settings
from core.errors.media_errors import http_error_storage_unavailable

# boto3 1.36+ manda checksum CRC32 che Tigris/Railway Bucket rifiutano su GetObject.
os.environ.setdefault("AWS_REQUEST_CHECKSUM_CALCULATION", "when_required")
os.environ.setdefault("AWS_RESPONSE_CHECKSUM_VALIDATION", "when_required")

logger = logging.getLogger(__name__)

_MEDIA_MOUNT = "/media"
_CONTENT_TYPES = {
    ".webp": "image/webp",
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".gif": "image/gif",
}


class StorageService:
    """Put/delete oggetti. Gli URL pubblici passano sempre da ``GET /media/{key}``."""

    def put_bytes(self, key: str, data: bytes, content_type: str) -> str:
        """Salva l'oggetto e restituisce l'URL pubblico su tn-be."""
        safe_key = _safe_key(key)
        settings = get_settings()
        try:
            if settings.storage_backend == "s3":
                _s3_put(safe_key, data, content_type)
            else:
                _local_put(safe_key, data)
        except Exception:
            logger.exception("storage.put_failed backend=%s key=%s", settings.storage_backend, safe_key)
            raise http_error_storage_unavailable() from None
        return public_url_for_key(safe_key)

    def read_bytes(self, key: str) -> tuple[bytes, str] | None:
        """Legge l'oggetto per ``GET /media``. ``None`` se assente."""
        try:
            safe_key = _safe_key(key)
        except ValueError:
            return None
        settings = get_settings()
        if settings.storage_backend == "s3":
            return _s3_get(safe_key)
        path = local_storage_dir() / safe_key
        if not path.is_file():
            return None
        return path.read_bytes(), _content_type_for_key(safe_key)

    def delete_if_managed(self, url: str | None) -> None:
        """Elimina l'oggetto solo se l'URL è nostro (non foto Google/LinkedIn)."""
        key = key_from_public_url(url)
        if not key:
            return
        settings = get_settings()
        try:
            if settings.storage_backend == "s3":
                _s3_delete(key)
            else:
                _local_delete(key)
        except Exception:
            logger.warning("storage.delete_failed key=%s", key, exc_info=True)

    def delete_prefix(self, prefix: str) -> None:
        """Elimina tutti gli oggetti sotto un prefisso (es. ``avatars/{user_id}/``)."""
        folder = f"{_safe_key(prefix.strip().strip('/'))}/"
        settings = get_settings()
        try:
            if settings.storage_backend == "s3":
                _s3_delete_prefix(folder)
            else:
                _local_delete_prefix(folder)
        except Exception:
            logger.warning("storage.delete_prefix_failed prefix=%s", folder, exc_info=True)


def public_url_for_key(key: str) -> str:
    """URL stabile: sempre il host pubblico di tn-be (il bucket Railway è privato)."""
    settings = get_settings()
    return f"{settings.public_api_url}{_MEDIA_MOUNT}/{_safe_key(key)}"


def public_asset_url(url: str | None) -> str | None:
    """Riscrive gli URL ``/media/`` sul PUBLIC_API_URL corrente; lascia invariati gli URL esterni."""
    raw = (url or "").strip()
    if not raw:
        return None
    key = key_from_public_url(raw)
    if key:
        return public_url_for_key(key)
    return raw


def _canonicalize_media_url(value: object) -> object:
    if value is None or not isinstance(value, str):
        return value
    return public_asset_url(value)


PublicMediaUrl = Annotated[str | None, BeforeValidator(_canonicalize_media_url)]


def key_from_public_url(url: str | None) -> str | None:
    """Estrae la key da qualsiasi URL che contiene ``/media/`` (anche localhost salvato per errore)."""
    raw = (url or "").strip()
    if not raw:
        return None
    marker = f"{_MEDIA_MOUNT}/"
    idx = raw.find(marker)
    if idx < 0:
        return None
    key = raw[idx + len(marker) :].split("?", 1)[0].split("#", 1)[0]
    try:
        return _safe_key(key) if key else None
    except ValueError:
        return None


def local_storage_dir() -> Path:
    """Directory file locale (creata al bisogno)."""
    path = Path(get_settings().storage_local_dir)
    if not path.is_absolute():
        path = Path.cwd() / path
    path.mkdir(parents=True, exist_ok=True)
    return path


@lru_cache
def get_storage_service() -> StorageService:
    return StorageService()


def _safe_key(key: str) -> str:
    cleaned = key.strip().lstrip("/")
    parts = [part for part in cleaned.split("/") if part and part != "."]
    if not parts or any(part == ".." for part in parts):
        raise ValueError("invalid storage key")
    return "/".join(parts)


def _content_type_for_key(key: str) -> str:
    suffix = Path(key).suffix.lower()
    return _CONTENT_TYPES.get(suffix, "application/octet-stream")


def _local_put(key: str, data: bytes) -> None:
    dest = local_storage_dir() / key
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(data)


def _local_delete(key: str) -> None:
    dest = local_storage_dir() / key
    dest.unlink(missing_ok=True)


def _s3_client(*, addressing_style: str):
    import boto3
    from botocore.config import Config as BotoConfig

    settings = get_settings()
    config_kwargs: dict[str, object] = {
        "s3": {"addressing_style": addressing_style},
        "signature_version": "s3v4",
        "request_checksum_calculation": "when_required",
        "response_checksum_validation": "when_required",
    }
    try:
        boto_config = BotoConfig(**config_kwargs)
    except TypeError:
        boto_config = BotoConfig(
            s3={"addressing_style": addressing_style},
            signature_version="s3v4",
        )
    kwargs: dict[str, object] = {
        "aws_access_key_id": settings.s3_access_key_id,
        "aws_secret_access_key": settings.s3_secret_access_key,
        "region_name": settings.s3_region or "auto",
        "config": boto_config,
    }
    if settings.s3_endpoint_url:
        kwargs["endpoint_url"] = settings.s3_endpoint_url
    return boto3.client("s3", **kwargs)


def _s3_put(key: str, data: bytes, content_type: str) -> None:
    settings = get_settings()
    _s3_client(addressing_style=settings.s3_addressing_style).put_object(
        Bucket=settings.s3_bucket,
        Key=key,
        Body=data,
        ContentType=content_type,
        CacheControl="public, max-age=31536000, immutable",
    )


def _s3_get(key: str) -> tuple[bytes, str] | None:
    settings = get_settings()
    primary = settings.s3_addressing_style
    other = "path" if primary == "virtual" else "virtual"
    for style in (primary, other):
        found = _s3_get_with_style(key, style)
        if found is not None:
            if style != primary:
                logger.warning("storage.get_ok_via_fallback key=%s style=%s", key, style)
            return found
    return None


def _s3_get_with_style(key: str, addressing_style: str) -> tuple[bytes, str] | None:
    from botocore.exceptions import ClientError

    settings = get_settings()
    try:
        response = _s3_client(addressing_style=addressing_style).get_object(
            Bucket=settings.s3_bucket,
            Key=key,
        )
    except ClientError as exc:
        code = str(exc.response.get("Error", {}).get("Code", ""))
        logger.warning("storage.get_miss key=%s style=%s code=%s", key, addressing_style, code)
        return None
    except Exception:
        logger.exception("storage.get_failed key=%s style=%s", key, addressing_style)
        raise http_error_storage_unavailable() from None
    body = response["Body"].read()
    content_type = str(response.get("ContentType") or "").strip() or _content_type_for_key(key)
    return body, content_type


def _s3_delete(key: str) -> None:
    settings = get_settings()
    _s3_client(addressing_style=settings.s3_addressing_style).delete_object(
        Bucket=settings.s3_bucket,
        Key=key,
    )


def _local_delete_prefix(prefix: str) -> None:
    root = local_storage_dir().resolve()
    target = (root / prefix.strip("/")).resolve()
    if target != root and root not in target.parents:
        return
    if target.is_dir():
        shutil.rmtree(target, ignore_errors=True)


def _s3_delete_prefix(prefix: str) -> None:
    settings = get_settings()
    client = _s3_client(addressing_style=settings.s3_addressing_style)
    token: str | None = None
    while True:
        kwargs: dict[str, object] = {"Bucket": settings.s3_bucket, "Prefix": prefix}
        if token:
            kwargs["ContinuationToken"] = token
        response = client.list_objects_v2(**kwargs)
        objects = [{"Key": item["Key"]} for item in response.get("Contents", []) if item.get("Key")]
        if objects:
            client.delete_objects(
                Bucket=settings.s3_bucket,
                Delete={"Objects": objects, "Quiet": True},
            )
        if not response.get("IsTruncated"):
            return
        token = response.get("NextContinuationToken")
