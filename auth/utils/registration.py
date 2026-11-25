"""Stato registrazione / wizard onboarding."""

from __future__ import annotations

import uuid

from sqlalchemy.orm import Session

from auth.models.user import AuthUser
from config import UserStatus
from core.models.profile import CoreProfile


def is_registration_complete(db: Session, user_id: uuid.UUID) -> bool:
    """True se l'account è operativo (wizard/verifica fatti, o utente importato WP).

    Gli interessi non sono obbligatori: bastano ``status=active`` e un profilo.
    """
    user = db.get(AuthUser, user_id)
    if user is None or user.status != UserStatus.ACTIVE:
        return False
    profile = db.get(CoreProfile, user_id)
    return profile is not None


def is_oauth_pending_user(user: AuthUser) -> bool:
    """Utente creato/collegato via OAuth, wizard non ancora completato."""
    return user.status == UserStatus.PENDING and user.password_hash is None


def is_email_password_pending_user(user: AuthUser) -> bool:
    """Signup classico in attesa di verifica email."""
    return user.status == UserStatus.PENDING and user.password_hash is not None


def pending_signup_reason(user: AuthUser) -> str | None:
    """Motivo dello ``status=pending`` (verifica email vs onboarding OAuth)."""
    if user.status != UserStatus.PENDING:
        return None
    if is_email_password_pending_user(user):
        return "email_verification"
    if is_oauth_pending_user(user):
        return "oauth_onboarding"
    return "incomplete"
