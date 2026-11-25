"""Export CSV utenti per la console super admin."""

from __future__ import annotations

import csv
import io
import uuid
from datetime import UTC, date, datetime
from enum import Enum

from sqlalchemy.orm import Session

from admin.schemas.users import UserExportColumn, UserExportMode
from admin.services.audience_merge import MergedContact, load_merged_contacts
from admin.services.user_admin_service import (
    _load_accepted_connection_counts,
    _load_invites_map,
    _load_roles_map,
)
from auth.models.user import AuthUser
from config.constants import AuditModule
from core.models.interest import CoreInterest
from core.models.user_interest import CoreUserInterest
from sqlalchemy import select

CSV_HEADERS: dict[UserExportColumn, str] = {
    UserExportColumn.ID: "ID",
    UserExportColumn.EMAIL: "Email",
    UserExportColumn.USERNAME: "Username",
    UserExportColumn.FIRST_NAME: "Nome",
    UserExportColumn.LAST_NAME: "Cognome",
    UserExportColumn.STATUS: "Stato",
    UserExportColumn.ROLES: "Ruoli",
    UserExportColumn.CREATED_AT: "Iscrizione",
    UserExportColumn.EMAIL_VERIFIED_AT: "Email verificata",
    UserExportColumn.REFERRAL_CODE: "Codice invito",
    UserExportColumn.INVITED_BY_USERNAME: "Invitato da",
    UserExportColumn.BIRTH_DATE: "Data di nascita",
    UserExportColumn.GENDER: "Genere",
    UserExportColumn.RESIDENCE_COUNTRY: "Paese",
    UserExportColumn.RESIDENCE_CITY: "Città",
    UserExportColumn.BIO: "Bio",
    UserExportColumn.CURRENT_COMPANY_NAME: "Azienda",
    UserExportColumn.CURRENT_JOB_POSITION: "Ruolo lavorativo",
    UserExportColumn.LINKEDIN_URL: "LinkedIn",
    UserExportColumn.INTERESTS: "Interessi",
    UserExportColumn.INVITES_COUNT: "Inviti",
    UserExportColumn.CONNECTIONS_ACCEPTED: "Connessioni",
    UserExportColumn.PROFILE_COMPLETENESS: "Completezza profilo",
}

GLOBAL_COLUMNS = list(UserExportColumn)


def resolve_export_columns(mode: UserExportMode, columns: list[UserExportColumn] | None) -> list[UserExportColumn]:
    """Colonne effettive: globale = tutte; mailing = set dedicato; custom = scelta."""
    if mode == UserExportMode.GLOBAL:
        return list(GLOBAL_COLUMNS)
    unique: list[UserExportColumn] = []
    seen: set[UserExportColumn] = set()
    for column in columns or []:
        if column not in seen:
            unique.append(column)
            seen.add(column)
    return unique


def build_users_csv(
    db: Session,
    *,
    actor: AuthUser,
    mode: UserExportMode,
    columns: list[UserExportColumn] | None,
) -> tuple[bytes, str]:
    """Genera il CSV e registra l'azione nel log console."""
    selected = resolve_export_columns(mode, columns)
    contacts, brevo_synced = load_merged_contacts(db)

    platform_contacts = [row for row in contacts if row.user is not None]
    user_ids = [row.user.id for row in platform_contacts if row.user is not None]
    column_set = set(selected)

    roles_by_user = _load_roles_map(db, user_ids) if UserExportColumn.ROLES in column_set else {}
    invites_by_user = (
        _load_invites_map(db, user_ids) if UserExportColumn.INVITES_COUNT in column_set else {}
    )
    connections_by_user = (
        _load_accepted_connection_counts(db, user_ids)
        if UserExportColumn.CONNECTIONS_ACCEPTED in column_set
        else {}
    )
    inviter_usernames = (
        _load_inviter_usernames(db, [row.user.invited_by_id for row in platform_contacts if row.user])
        if UserExportColumn.INVITED_BY_USERNAME in column_set
        else {}
    )
    interests_by_user = (
        _load_interests_map(db, user_ids) if UserExportColumn.INTERESTS in column_set else {}
    )

    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow([CSV_HEADERS[column] for column in selected])
    for contact in contacts:
        user = contact.user
        profile = contact.profile
        writer.writerow(
            [
                _cell_value(
                    column,
                    contact=contact,
                    roles=roles_by_user.get(user.id, []) if user is not None else [],
                    invites_count=invites_by_user.get(user.id, 0) if user is not None else 0,
                    connections_accepted=connections_by_user.get(user.id, 0) if user is not None else 0,
                    invited_by_username=(
                        inviter_usernames.get(user.invited_by_id) if user is not None and user.invited_by_id else None
                    ),
                    interests=interests_by_user.get(user.id, []) if user is not None else [],
                )
                for column in selected
            ]
        )

    from admin.services.audit_log import record_audit

    record_audit(
        db,
        module=AuditModule.USERS,
        action="user.exported",
        message=_audit_message(mode, len(contacts)),
        actor=actor,
        target_type="users",
        payload={
            "mode": mode.value,
            "columns": [column.value for column in selected],
            "row_count": len(contacts),
            "brevo_synced": brevo_synced,
        },
    )
    db.commit()

    payload = ("\ufeff" + buffer.getvalue()).encode("utf-8")
    return payload, _filename(mode)


def _profile_first_name(contact: MergedContact) -> str | None:
    profile = contact.profile
    if profile is not None and profile.first_name:
        return profile.first_name
    return contact.brevo_first_name


def _profile_last_name(contact: MergedContact) -> str | None:
    profile = contact.profile
    if profile is not None and profile.last_name:
        return profile.last_name
    return contact.brevo_last_name


def _cell_value(
    column: UserExportColumn,
    *,
    contact: MergedContact,
    roles: list[str],
    invites_count: int,
    connections_accepted: int,
    invited_by_username: str | None,
    interests: list[str],
) -> str:
    user = contact.user
    profile = contact.profile
    if user is None:
        values: dict[UserExportColumn, object] = {
            UserExportColumn.ID: None,
            UserExportColumn.EMAIL: contact.email,
            UserExportColumn.USERNAME: None,
            UserExportColumn.FIRST_NAME: _profile_first_name(contact),
            UserExportColumn.LAST_NAME: _profile_last_name(contact),
            UserExportColumn.STATUS: None,
            UserExportColumn.ROLES: None,
            UserExportColumn.CREATED_AT: None,
            UserExportColumn.EMAIL_VERIFIED_AT: None,
            UserExportColumn.REFERRAL_CODE: None,
            UserExportColumn.INVITED_BY_USERNAME: None,
            UserExportColumn.BIRTH_DATE: None,
            UserExportColumn.GENDER: None,
            UserExportColumn.RESIDENCE_COUNTRY: None,
            UserExportColumn.RESIDENCE_CITY: None,
            UserExportColumn.BIO: None,
            UserExportColumn.CURRENT_COMPANY_NAME: None,
            UserExportColumn.CURRENT_JOB_POSITION: None,
            UserExportColumn.LINKEDIN_URL: None,
            UserExportColumn.INTERESTS: None,
            UserExportColumn.INVITES_COUNT: None,
            UserExportColumn.CONNECTIONS_ACCEPTED: None,
            UserExportColumn.PROFILE_COMPLETENESS: None,
        }
        return _stringify(values[column])

    values = {
        UserExportColumn.ID: user.id,
        UserExportColumn.EMAIL: user.email,
        UserExportColumn.USERNAME: user.username,
        UserExportColumn.FIRST_NAME: _profile_first_name(contact),
        UserExportColumn.LAST_NAME: _profile_last_name(contact),
        UserExportColumn.STATUS: user.status.value if isinstance(user.status, Enum) else user.status,
        UserExportColumn.ROLES: "; ".join(roles),
        UserExportColumn.CREATED_AT: user.created_at,
        UserExportColumn.EMAIL_VERIFIED_AT: user.email_verified_at,
        UserExportColumn.REFERRAL_CODE: user.referral_code,
        UserExportColumn.INVITED_BY_USERNAME: invited_by_username,
        UserExportColumn.BIRTH_DATE: profile.birth_date if profile is not None else None,
        UserExportColumn.GENDER: profile.gender if profile is not None else None,
        UserExportColumn.RESIDENCE_COUNTRY: profile.residence_country if profile is not None else None,
        UserExportColumn.RESIDENCE_CITY: profile.residence_city if profile is not None else None,
        UserExportColumn.BIO: profile.bio if profile is not None else None,
        UserExportColumn.CURRENT_COMPANY_NAME: profile.current_company_name if profile is not None else None,
        UserExportColumn.CURRENT_JOB_POSITION: profile.current_job_position if profile is not None else None,
        UserExportColumn.LINKEDIN_URL: profile.linkedin_url if profile is not None else None,
        UserExportColumn.INTERESTS: "; ".join(interests),
        UserExportColumn.INVITES_COUNT: invites_count,
        UserExportColumn.CONNECTIONS_ACCEPTED: connections_accepted,
        UserExportColumn.PROFILE_COMPLETENESS: profile.profile_completeness if profile is not None else None,
    }
    return _stringify(values[column])


def _stringify(value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, uuid.UUID):
        return str(value)
    if isinstance(value, Enum):
        return str(value.value)
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)


def _load_inviter_usernames(db: Session, inviter_ids: list[uuid.UUID | None]) -> dict[uuid.UUID, str]:
    ids = [inviter_id for inviter_id in inviter_ids if inviter_id is not None]
    if not ids:
        return {}
    rows = db.execute(select(AuthUser.id, AuthUser.username).where(AuthUser.id.in_(ids))).all()
    return {user_id: str(username) for user_id, username in rows}


def _load_interests_map(db: Session, user_ids: list[uuid.UUID]) -> dict[uuid.UUID, list[str]]:
    if not user_ids:
        return {}
    rows = db.execute(
        select(CoreUserInterest.user_id, CoreInterest.name)
        .join(CoreInterest, CoreInterest.id == CoreUserInterest.interest_id)
        .where(CoreUserInterest.user_id.in_(user_ids))
        .order_by(CoreInterest.name.asc())
    ).all()
    mapped: dict[uuid.UUID, list[str]] = {user_id: [] for user_id in user_ids}
    for user_id, name in rows:
        mapped.setdefault(user_id, []).append(str(name))
    return mapped


def _filename(mode: UserExportMode) -> str:
    stamp = datetime.now(UTC).strftime("%Y%m%d")
    if mode == UserExportMode.CUSTOM:
        return f"utenti-custom-{stamp}.csv"
    return f"utenti-{stamp}.csv"


def _audit_message(mode: UserExportMode, row_count: int) -> str:
    if mode == UserExportMode.CUSTOM:
        return f"Export utenti personalizzato ({row_count} righe)"
    return f"Export utenti globale ({row_count} righe)"
