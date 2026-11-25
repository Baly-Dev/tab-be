"""Auth helpers (hashing, token, dependency utente corrente)."""

from auth.utils.helpers import (
    AuthenticatedUser,
    bearer_scheme,
    bearer_scheme_required,
    get_current_user,
    hash_password,
    needs_rehash,
    upgrade_password_hash_if_needed,
    user_from_access_token,
    verify_password,
)

__all__ = [
    "AuthenticatedUser",
    "bearer_scheme",
    "bearer_scheme_required",
    "get_current_user",
    "hash_password",
    "needs_rehash",
    "upgrade_password_hash_if_needed",
    "user_from_access_token",
    "verify_password",
]
