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
    """Ruoli applicativi (più ruoli per utente in ``core_user_roles``).

    ``professional`` è la persona consumer. ``admin`` / ``super_admin`` sono stewardship TAB.
    Host di un tavolo non è un ruolo account: è un comportamento sul tavolo.
    """

    SUPER_ADMIN = "super_admin"
    ADMIN = "admin"
    PROFESSIONAL = "professional"


class VenueStatus(str, enum.Enum):
    """Pubblicazione scheda locale."""

    DRAFT = "draft"
    PUBLISHED = "published"
    SUSPENDED = "suspended"


class VenuePriceBand(str, enum.Enum):
    """Fascia prezzo stile OpenTable (``$`` … ``$$$$``)."""

    MODEST = "1"
    MODERATE = "2"
    EXPENSIVE = "3"
    VERY_EXPENSIVE = "4"


class VenueMenuKind(str, enum.Enum):
    """Tipo di carta pubblicata dal locale."""

    LUNCH = "lunch"
    DINNER = "dinner"
    FLASH = "flash"
    OTHER = "other"


class PartyKind(str, enum.Enum):
    """Prenotazione da solo oppure attorno a un gruppo."""

    SOLO = "solo"
    GROUP = "group"


class BookingStatus(str, enum.Enum):
    """Stato della prenotazione presso il locale."""

    DRAFT = "draft"
    REQUESTED = "requested"
    CONFIRMED = "confirmed"
    DECLINED = "declined"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class OrderStatus(str, enum.Enum):
    """Stato dell'ordine (il coperto impegnato su un menu)."""

    DRAFT = "draft"
    PLACED = "placed"
    CANCELLED = "cancelled"


class PaymentMethod(str, enum.Enum):
    """Come si paga il coperto. Il pranzo ordinario è al locale, la flash in app."""

    PAY_AT_VENUE = "pay_at_venue"
    CARD = "card"
    MEAL_VOUCHER = "meal_voucher"


class PaymentStatus(str, enum.Enum):
    """Stato del pagamento sull'ordine."""

    UNPAID = "unpaid"
    PENDING = "pending"
    PAID = "paid"
    FAILED = "failed"
    REFUNDED = "refunded"


class SubscriptionStatus(str, enum.Enum):
    """Canone del locale verso TAB."""

    INACTIVE = "inactive"
    ACTIVE = "active"


class GroupStatus(str, enum.Enum):
    """Raccolta adesioni del gruppo."""

    OPEN = "open"
    LOCKED = "locked"
    CLOSED = "closed"


class GroupMemberRole(str, enum.Enum):
    """Ruolo dentro un gruppo, non sull'account."""

    HOST = "host"
    GUEST = "guest"


class GroupInviteStatus(str, enum.Enum):
    """Invito di un professional a un gruppo."""

    PENDING = "pending"
    ACCEPTED = "accepted"
    DECLINED = "declined"
    REVOKED = "revoked"


class VenueStaffRole(str, enum.Enum):
    """Operatore di un venue. L'account resta un ``professional``."""

    OWNER = "owner"
    MANAGER = "manager"
    STAFF = "staff"


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
