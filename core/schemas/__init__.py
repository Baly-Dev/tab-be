"""Schemi Pydantic del modulo core."""

from core.schemas.connection import (
    ConnectionListResponse,
    ConnectionPeerResponse,
    ConnectionResponse,
    CreateConnectionRequest,
)
from core.schemas.invites import SignupInviteeItem, SignupInviteesListResponse
from core.schemas.interest import InterestCategoryGroup, InterestItem, InterestListResponse
from core.schemas.me import (
    MeConnectionsSummary,
    MeInterestItem,
    MeProfileResponse,
    MeResponse,
)
from core.schemas.member_search import MemberSearchItem, MemberSearchResponse
from core.schemas.public_profile import (
    PublicProfileInterestItem,
    PublicProfileResponse,
    ViewerConnectionContext,
)
from core.schemas.user_connections import (
    ProfileConnectionPeerResponse,
    ProfileConnectionsListResponse,
)

__all__ = [
    "ConnectionListResponse",
    "ConnectionPeerResponse",
    "ConnectionResponse",
    "CreateConnectionRequest",
    "SignupInviteeItem",
    "SignupInviteesListResponse",
    "InterestCategoryGroup",
    "InterestItem",
    "InterestListResponse",
    "MeConnectionsSummary",
    "MeInterestItem",
    "MeProfileResponse",
    "MeResponse",
    "MemberSearchItem",
    "MemberSearchResponse",
    "PublicProfileInterestItem",
    "PublicProfileResponse",
    "ProfileConnectionPeerResponse",
    "ProfileConnectionsListResponse",
    "ViewerConnectionContext",
]
