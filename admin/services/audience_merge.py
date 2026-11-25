"""Unione contatti piattaforma + Brevo (deduplica per email)."""

from __future__ import annotations

import logging
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from auth.models.user import AuthUser
from config.constants import UserStatus
from core.models.profile import CoreProfile
from services.brevo_contacts import BrevoContactRow, BrevoContactsClient, BrevoContactsError, get_brevo_contacts_client

logger = logging.getLogger(__name__)


def normalize_email(email: str) -> str:
    return email.strip().lower()


@dataclass(frozen=True, slots=True)
class MergedContact:
    """Riga audience/export: account piattaforma o solo Brevo."""

    email: str
    user: AuthUser | None = None
    profile: CoreProfile | None = None
    brevo_first_name: str | None = None
    brevo_last_name: str | None = None


def _load_platform_contacts(db: Session) -> list[MergedContact]:
    stmt = (
        select(AuthUser, CoreProfile)
        .outerjoin(CoreProfile, CoreProfile.user_id == AuthUser.id)
        .where(AuthUser.status != UserStatus.DELETED)
        .order_by(AuthUser.created_at.desc())
    )
    rows = db.execute(stmt).all()
    contacts: list[MergedContact] = []
    for user, profile in rows:
        email = str(user.email).strip()
        if not email:
            continue
        contacts.append(MergedContact(email=email, user=user, profile=profile))
    return contacts


def _fetch_brevo_contacts(client: BrevoContactsClient) -> tuple[list[BrevoContactRow], bool]:
    if not client.is_configured:
        return [], False
    try:
        return client.fetch_all(), True
    except BrevoContactsError:
        logger.exception("Unable to fetch Brevo contacts for merge")
        return [], False


def load_merged_contacts(
    db: Session,
    *,
    brevo_client: BrevoContactsClient | None = None,
) -> tuple[list[MergedContact], bool]:
    """Utenti piattaforma + contatti Brevo la cui email non è già in piattaforma."""
    client = brevo_client or get_brevo_contacts_client()
    platform = _load_platform_contacts(db)
    seen = {normalize_email(row.email) for row in platform}
    brevo_rows, brevo_synced = _fetch_brevo_contacts(client)
    merged = list(platform)
    for contact in brevo_rows:
        key = normalize_email(contact.email)
        if key in seen:
            continue
        seen.add(key)
        merged.append(
            MergedContact(
                email=contact.email.strip(),
                brevo_first_name=contact.first_name,
                brevo_last_name=contact.last_name,
            )
        )
    return merged, brevo_synced
