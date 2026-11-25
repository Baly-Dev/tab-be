"""
ORM shim: ``Base`` + models for Alembic and legacy ``from db import …``.

- Models: ``auth.models``
- Enums: ``config.constants``
- ``Base``: ``config.db``
"""

import auth.models  # noqa: F401 — register Auth mappers on ``Base.metadata``.

from auth.models import (
    AuthPasswordResetToken,
    AuthRefreshToken,
    AuthSocialAccount,
    AuthUser,
    AuthUserRole,
    AuthWebAuthnCredential,
)
from config.constants import AppRole, OAuthProvider, UserStatus
from config.db import Base

__all__ = [
    "AppRole",
    "AuthPasswordResetToken",
    "AuthRefreshToken",
    "AuthSocialAccount",
    "AuthUser",
    "AuthUserRole",
    "AuthWebAuthnCredential",
    "Base",
    "OAuthProvider",
    "UserStatus",
]
