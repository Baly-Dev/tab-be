"""
ORM shim: ``Base`` + modelli per Alembic e import legacy ``from db import …``.

- Modelli: ``auth.models``, ``core.models`` (``admin`` e ``notifications`` in scaffolding)
- Enum: ``config.constants``
- ``Base``: ``config.db``
"""

import auth.models  # noqa: F401 — registra i mapper Auth su ``Base.metadata``.
import core.models  # noqa: F401 — registra i mapper Core su ``Base.metadata``.

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
    OAuthProvider,
    UserStatus,
)
from config.db import Base
from core.models import (
    CoreVenueShift,
    CoreVenueShiftOverride,
    CoreBooking,
    CoreGroup,
    CoreGroupInvite,
    CoreGroupMember,
    CoreInterest,
    CoreInterestCategory,
    CoreOrganization,
    CoreOrganizationAffiliation,
    CoreProfile,
    CoreOrder,
    CoreProfileConnection,
    CoreUserInterest,
    CoreUserRole,
    CoreVenue,
    CoreVenueImage,
    CoreVenueMembership,
    CoreVenueMenu,
    CoreVenueMenuImage,
    CoreVenueMenuWindow,
)
from core.utils.connections import ordered_profile_connection_pair

__all__ = [
    "AppRole",
    "AuthPasswordResetToken",
    "AuthRefreshToken",
    "AuthSocialAccount",
    "AuthUser",
    "AuthWebAuthnCredential",
    "Base",
    "ConnectionStatus",
    "CoreVenueShift",
    "CoreVenueShiftOverride",
    "CoreBooking",
    "CoreGroup",
    "CoreGroupInvite",
    "CoreGroupMember",
    "CoreInterest",
    "CoreInterestCategory",
    "CoreOrganization",
    "CoreOrganizationAffiliation",
    "CoreProfile",
    "CoreOrder",
    "CoreProfileConnection",
    "CoreUserInterest",
    "CoreUserRole",
    "CoreVenue",
    "CoreVenueImage",
    "CoreVenueMembership",
    "CoreVenueMenu",
    "CoreVenueMenuImage",
    "CoreVenueMenuWindow",
    "Gender",
    "OAuthProvider",
    "UserStatus",
    "ordered_profile_connection_pair",
]