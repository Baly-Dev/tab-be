"""Minimal env so importing app modules under pytest does not require a local .env."""

from __future__ import annotations

import os

os.environ.setdefault("APP_ENV", "local")
os.environ.setdefault("JWT_SECRET", "pytest-jwt-secret")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")
os.environ.setdefault(
    "DATABASE_URL",
    "postgresql+psycopg://postgres:postgres@127.0.0.1:5432/tn_be",
)