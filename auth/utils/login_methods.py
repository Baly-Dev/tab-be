"""Conteggio metodi di accesso (password, OAuth, passkey)."""

from __future__ import annotations

import uuid

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from auth.models.social_account import AuthSocialAccount
from auth.models.user import AuthUser
from auth.models.webauthn_credential import AuthWebAuthnCredential
from config import OAuthProvider


def count_login_methods(
    db: Session,
    user: AuthUser,
    *,
    exclude_provider: OAuthProvider | None = None,
    exclude_passkey_id: uuid.UUID | None = None,
) -> int:
    """Quanti metodi restano per accedere. Usato per non lasciare l'account senza login."""
    total = 1 if user.password_hash else 0

    social_query = (
        select(func.count())
        .select_from(AuthSocialAccount)
        .where(AuthSocialAccount.user_id == user.id)
    )
    if exclude_provider is not None:
        social_query = social_query.where(AuthSocialAccount.provider != exclude_provider)
    total += int(db.scalar(social_query) or 0)

    passkey_query = (
        select(func.count())
        .select_from(AuthWebAuthnCredential)
        .where(AuthWebAuthnCredential.user_id == user.id)
    )
    if exclude_passkey_id is not None:
        passkey_query = passkey_query.where(AuthWebAuthnCredential.id != exclude_passkey_id)
    total += int(db.scalar(passkey_query) or 0)

    return total
