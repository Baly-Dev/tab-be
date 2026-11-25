"""Hook for personal data that would live outside ``auth_users`` CASCADE.

This service only stores identity on auth tables, so deletion has nothing else to scrub.
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from auth.models.user import AuthUser


def erase_retained_personal_data(db: Session, user: AuthUser) -> None:
    """No-op: profiles, notifications, and audit logs are not part of this service."""
    _ = (db, user)
