"""Inviti iscrizione (growth): codice ``?ref=``, attribution, connessione invitante."""

from __future__ import annotations

import logging
import uuid

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from auth.models.user import AuthUser
from config import UserStatus
from core.utils.connections import ensure_accepted_connection
from core.utils.roles import can_invite_to_platform, load_user_roles

logger = logging.getLogger(__name__)


def resolve_inviter_id(db: Session, inviter_code: str | None) -> uuid.UUID | None:
    """Risolve ``referral_code`` in un invitante eleggibile (connector+ attivo)."""
    code = (inviter_code or "").strip().upper()
    if not code:
        return None
    inviter = db.scalar(select(AuthUser).where(AuthUser.referral_code == code))
    if inviter is None:
        logger.warning("signup.unknown_referral_code code=%s", code)
        return None
    if inviter.status != UserStatus.ACTIVE:
        logger.warning("signup.inactive_inviter user_id=%s code=%s", inviter.id, code)
        return None
    roles = load_user_roles(db, inviter.id)
    if not can_invite_to_platform(roles):
        logger.warning("signup.ineligible_inviter user_id=%s code=%s", inviter.id, code)
        return None
    return inviter.id


def count_signup_invites(db: Session, inviter_id: uuid.UUID) -> int:
    """Utenti attribuiti all'invitante (esclusi account eliminati)."""
    count = db.scalar(
        select(func.count())
        .select_from(AuthUser)
        .where(
            AuthUser.invited_by_id == inviter_id,
            AuthUser.status != UserStatus.DELETED,
        )
    )
    return int(count or 0)


def connect_signup_inviter(db: Session, user: AuthUser) -> None:
    """Connessione ``accepted`` silenziosa con chi ha invitato alla signup."""
    inviter_id = user.invited_by_id
    if inviter_id is None or inviter_id == user.id:
        return
    ensure_accepted_connection(
        db,
        user.id,
        inviter_id,
        initiated_by_id=inviter_id,
    )
    logger.info("signup.invite_connected invitee_id=%s inviter_id=%s", user.id, inviter_id)
