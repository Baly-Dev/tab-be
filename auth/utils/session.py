"""Issue an access + refresh pair after login / refresh."""

from __future__ import annotations

from sqlalchemy.orm import Session

from auth.models.user import AuthUser
from auth.schemas.login import AuthUserBrief, TokenResponse
from auth.utils.roles import load_user_roles
from auth.utils.tokens import (
    create_access_token,
    generate_refresh_token_plain,
    persist_refresh_token,
)


def issue_token_pair(db: Session, user: AuthUser) -> tuple[str, str, int]:
    """Create an access JWT and a persisted opaque refresh token."""
    roles = load_user_roles(db, user.id)
    access, expires_in = create_access_token(
        user_id=user.id,
        email=str(user.email),
        roles=roles,
    )
    refresh_plain = generate_refresh_token_plain()
    persist_refresh_token(db, user_id=user.id, plain=refresh_plain)
    return access, refresh_plain, expires_in


def build_token_response(db: Session, user: AuthUser) -> TokenResponse:
    """Token payload shared by login and refresh (commit is the caller's job)."""
    access, refresh_plain, expires_in = issue_token_pair(db, user)
    return TokenResponse(
        access_token=access,
        refresh_token=refresh_plain,
        expires_in=expires_in,
        user=AuthUserBrief(
            id=user.id,
            email=str(user.email),
            username=str(user.username),
            status=user.status.value,
        ),
    )
