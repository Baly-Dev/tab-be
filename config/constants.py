"""Shared enums used by the auth system."""

import enum


class UserStatus(enum.Enum):
    ACTIVE = "active"
    PENDING = "pending"
    SUSPENDED = "suspended"
    DELETED = "deleted"


class OAuthProvider(str, enum.Enum):
    GOOGLE = "google"
    LINKEDIN = "linkedin"


class AppRole(str, enum.Enum):
    """Application roles (a user may hold more than one)."""

    SUPER_ADMIN = "super_admin"
    ADMIN = "admin"
    MEMBER = "member"
