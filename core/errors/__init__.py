"""Errori modulo Core (dominio + mapping HTTP)."""

from core.errors.connection_errors import (
    AlreadyConnectedError,
    CannotConnectToSelfError,
    ConnectionAlreadyPendingError,
    ConnectionBlockedError,
    ConnectionNotFoundError,
    ConnectionServiceError,
    EventAlertNotAllowedError,
    InvalidConnectionActionError,
    TargetUserNotFoundError,
    http_error_from_connection,
)
from core.errors.member_search_errors import (
    InvalidSearchQueryError,
    MemberSearchServiceError,
    SearchNotAllowedError,
    http_error_from_member_search,
)
from core.errors.profile_errors import (
    http_error_empty_update,
    http_error_for_own_profile_missing,
    http_error_for_profile_connections_forbidden,
    http_error_for_profile_not_found,
    http_error_invalid_interest_ids,
)

__all__ = [
    "AlreadyConnectedError",
    "CannotConnectToSelfError",
    "ConnectionAlreadyPendingError",
    "ConnectionBlockedError",
    "ConnectionNotFoundError",
    "ConnectionServiceError",
    "EventAlertNotAllowedError",
    "InvalidConnectionActionError",
    "InvalidSearchQueryError",
    "MemberSearchServiceError",
    "SearchNotAllowedError",
    "TargetUserNotFoundError",
    "http_error_empty_update",
    "http_error_for_own_profile_missing",
    "http_error_for_profile_connections_forbidden",
    "http_error_for_profile_not_found",
    "http_error_from_connection",
    "http_error_from_member_search",
    "http_error_invalid_interest_ids",
]
