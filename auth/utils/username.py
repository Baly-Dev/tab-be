"""Generazione username univoco (signup OAuth, ecc.)."""

from __future__ import annotations

import random
import re

from sqlalchemy import select
from sqlalchemy.orm import Session

from auth.models.user import AuthUser

_USERNAME_RE = re.compile(r"^[a-z0-9_]{3,32}$")
_MAX_ATTEMPTS = 50


def _normalize_name_part(s: str) -> str:
    """Lowercase, solo [a-z], strip."""
    return re.sub(r"[^a-z]", "", s.strip().lower())


def generate_unique_username(
    db: Session,
    email: str | None = None,
    *,
    first_name: str | None = None,
    last_name: str | None = None,
) -> str:
    """Genera ``nome_cognome_NNNN``. Mai derivato dall'email."""
    first = _normalize_name_part(first_name or "")
    last = _normalize_name_part(last_name or "")

    if first and last:
        base = f"{first}_{last}"[:27]
    elif first or last:
        base = (first or last)[:27]
    else:
        base = "user"

    if len(base) < 3:
        base = f"user_{base}"[:27]
    if len(base) < 3:
        base = "usr"

    for _ in range(_MAX_ATTEMPTS):
        digits = random.randint(1000, 9999)
        candidate = f"{base}_{digits}"
        if (
            _USERNAME_RE.fullmatch(candidate)
            and db.scalar(select(AuthUser.id).where(AuthUser.username == candidate)) is None
        ):
            return candidate

    # fallback: 6 cifre per spazio più ampio
    for _ in range(_MAX_ATTEMPTS):
        suffix = random.randint(100000, 999999)
        candidate = f"{base}_{suffix}"[:32]
        if (
            _USERNAME_RE.fullmatch(candidate)
            and db.scalar(select(AuthUser.id).where(AuthUser.username == candidate)) is None
        ):
            return candidate

    raise RuntimeError(f"Unable to generate unique username for base '{base}'")
