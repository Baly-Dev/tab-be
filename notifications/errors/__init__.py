"""Errori modulo Notifications (dominio + mapping HTTP)."""

from notifications.errors.notification_errors import (
    NotificationNotFoundError,
    NotificationServiceError,
    http_error_from_notification,
)

__all__ = [
    "NotificationNotFoundError",
    "NotificationServiceError",
    "http_error_from_notification",
]
