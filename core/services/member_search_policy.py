"""Policy ricerca membri (visibilità, permessi, filtri futuri)."""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from sqlalchemy import Select, and_, or_, select
from sqlalchemy.orm import Session

from auth.models.user import AuthUser
from auth.utils.registration import is_registration_complete
from config import UserStatus
from config.constants import ConnectionStatus
from core.errors.member_search_errors import SearchNotAllowedError
from core.models.connection import CoreProfileConnection
from core.permissions import Permission, user_has_permission


@dataclass(frozen=True)
class MemberSearchContext:
    """Contesto viewer per applicare policy di ricerca."""

    viewer_id: uuid.UUID


def assert_member_search_allowed(db: Session, viewer: AuthUser) -> MemberSearchContext:
    """Verifica che il viewer possa usare la ricerca membri.

    Estendere qui rate limiting, ruoli aggiuntivi o feature flags.
    """
    if not user_has_permission(db, viewer.id, Permission.MEMBERS_SEARCH):
        raise SearchNotAllowedError
    if viewer.status != UserStatus.ACTIVE:
        raise SearchNotAllowedError("Account is not active")
    if not is_registration_complete(db, viewer.id):
        raise SearchNotAllowedError("Complete your profile before searching members")
    return MemberSearchContext(viewer_id=viewer.id)


def apply_member_search_visibility(
    query: Select,
    *,
    context: MemberSearchContext,
) -> Select:
    """Applica filtri base di visibilità sul set di risultati.

    Estendere con filtri per ruolo, visibilità profilo, grafo, ecc.
    """
    _ = context
    blocked_with_viewer = (
        select(CoreProfileConnection.id)
        .where(
            CoreProfileConnection.status == ConnectionStatus.BLOCKED,
            or_(
                and_(
                    CoreProfileConnection.user_low_id == context.viewer_id,
                    CoreProfileConnection.user_high_id == AuthUser.id,
                ),
                and_(
                    CoreProfileConnection.user_high_id == context.viewer_id,
                    CoreProfileConnection.user_low_id == AuthUser.id,
                ),
            ),
        )
        .correlate(AuthUser)
    )
    return query.where(
        AuthUser.status == UserStatus.ACTIVE,
        AuthUser.id != context.viewer_id,
        ~blocked_with_viewer.exists(),
    )
