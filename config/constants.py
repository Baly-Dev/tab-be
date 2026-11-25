"""Shared enums (DB / domain constants) used across modules."""

import enum


class UserStatus(enum.Enum):
    ACTIVE = "active"
    PENDING = "pending"
    SUSPENDED = "suspended"
    DELETED = "deleted"


class OAuthProvider(str, enum.Enum):
    GOOGLE = "google"
    LINKEDIN = "linkedin"


class ConnectionStatus(enum.Enum):
    PENDING = "pending"
    ACCEPTED = "accepted"
    BLOCKED = "blocked"


class AppRole(str, enum.Enum):
    """Ruoli applicativi (più ruoli per utente in ``core_user_roles``)."""

    SUPER_ADMIN = "super_admin"
    ADMIN = "admin"
    CONNECTOR = "connector"
    MEMBER = "member"


class Gender(str, enum.Enum):
    """Genere profilo utente."""

    MALE = "male"
    FEMALE = "female"
    PREFER_NOT_TO_SAY = "prefer_not_to_say"


class AuditModule(str, enum.Enum):
    """Modulo di provenienza di un log consultabile in console."""

    AUTH = "auth"
    USERS = "users"
    NETWORK = "network"
    NOTIFICATIONS = "notifications"
    ADMIN = "admin"
    SYSTEM = "system"


class AuditLevel(str, enum.Enum):
    """Severità riga di log."""

    INFO = "info"
    WARNING = "warning"
    ERROR = "error"


class NotificationType(str, enum.Enum):
    """Tipo notifica in-app (template client + routing canali)."""

    CONNECTION_REQUEST = "connection_request"
    CONNECTION_ACCEPTED = "connection_accepted"
    PROFILE_INCOMPLETE = "profile_incomplete"
