"""Lettura UploadFile con limite di dimensione."""

from __future__ import annotations

from fastapi import UploadFile

from core.errors.media_errors import http_error_image_too_large, http_error_invalid_image

_CHUNK = 64 * 1024


def read_upload_bytes(file: UploadFile, *, max_bytes: int, max_mb: int) -> bytes:
    """Legge il file fino a ``max_bytes``; 413 se eccede, 422 se vuoto."""
    header_len = file.headers.get("content-length") if file.headers else None
    if header_len:
        try:
            if int(header_len) > max_bytes:
                raise http_error_image_too_large(max_mb=max_mb)
        except ValueError:
            pass

    chunks: list[bytes] = []
    total = 0
    while True:
        chunk = file.file.read(_CHUNK)
        if not chunk:
            break
        total += len(chunk)
        if total > max_bytes:
            raise http_error_image_too_large(max_mb=max_mb)
        chunks.append(chunk)
    data = b"".join(chunks)
    if not data:
        raise http_error_invalid_image()
    return data
