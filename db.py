"""
ORM shim: ``Base`` + modelli per Alembic e import legacy ``from db import …``.

- Modelli: ``auth.models``, ``core.models``, ``admin.models``, ``notifications.models``
- Enum: ``config.constants``
- ``Base``: ``config.db``
"""

import admin.models  # noqa: F401 — registra i mapper Admin su ``Base.metadata``.
import auth.models  # noqa: F401 — registra i mapper Auth su ``Base.metadata``.
import core.models  # noqa: F401 — registra i mapper Core su ``Base.metadata``.
import notifications.models  # noqa: F401 — registra i mapper Notifications su ``Base.metadata``.

from auth.models import (
    AuthPasswordResetToken,
    AuthRefreshToken,
    AuthSocialAccount,
    AuthUser,
    AuthWebAuthnCredential,
)
from config.constants import (
    AppRole,
    ConnectionStatus,
    Gender,
    NotificationType,
    OAuthProvider,
    UserStatus,
)
from config.db import Base
from core.models import (
    CoreInterest,
    CoreInterestCategory,
    CoreProfile,
    CoreProfileConnection,
    CoreUserInterest,
    CoreUserRole,
)
from core.utils.connections import ordered_profile_connection_pair
from notifications.models import Notification

__all__ = [
    "AppRole",
    "AuthPasswordResetToken",
    "AuthRefreshToken",
    "AuthSocialAccount",
    "AuthUser",
    "AuthWebAuthnCredential",
    "Base",
    "ConnectionStatus",
    "CoreInterest",
    "CoreInterestCategory",
    "CoreProfile",
    "CoreProfileConnection",
    "CoreUserInterest",
    "CoreUserRole",
    "Gender",
    "Notification",
    "NotificationType",
    "OAuthProvider",
    "UserStatus",
    "ordered_profile_connection_pair",
]
