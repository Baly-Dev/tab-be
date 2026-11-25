"""Registration / onboarding state."""

from __future__ import annotations

import uuid

from sqlalchemy.orm import Session

from auth.models.user import AuthUser
from config import UserStatus


def is_registration_complete(db: Session, user_id: uuid.UUID) -> bool:
    """True when the account is active (email verified or OAuth signup finished)."""
    user = db.get(AuthUser, user_id)
    return user is not None and user.status == UserStatus.ACTIVE


def is_oauth_pending_user(user: AuthUser) -> bool:
    """OAuth account whose signup has not been finished."""
    return user.status == UserStatus.PENDING and user.password_hash is None


def is_email_password_pending_user(user: AuthUser) -> bool:
    """Email/password signup waiting for email verification."""
    return user.status == UserStatus.PENDING and user.password_hash is not None


def pending_signup_reason(user: AuthUser) -> str | None:
    """Why ``status=pending`` (email verification vs OAuth onboarding)."""
    if user.status != UserStatus.PENDING:
        return None
    if is_email_password_pending_user(user):
        return "email_verification"
    if is_oauth_pending_user(user):
        return "oauth_onboarding"
    return "incomplete"
