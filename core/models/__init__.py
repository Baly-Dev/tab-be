"""SQLAlchemy models for the Core domain."""

from core.models.connection import CoreProfileConnection
from core.models.interest import CoreInterest
from core.models.interest_category import CoreInterestCategory
from core.models.profile import CoreProfile
from core.models.user_interest import CoreUserInterest
from core.models.user_role import CoreUserRole

__all__ = [
    "CoreInterest",
    "CoreInterestCategory",
    "CoreProfile",
    "CoreProfileConnection",
    "CoreUserInterest",
    "CoreUserRole",
]
