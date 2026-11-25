"""Utenti in console admin."""

from __future__ import annotations

import re
import uuid

from sqlalchemy import delete, func, or_, select
from sqlalchemy.orm import Session

from admin.errors import (
    AdminForbiddenMutationError,
    AdminInvalidRolesError,
    AdminUserNotFoundError,
)
from admin.schemas.users import (
    AdminUserDeletedResponse,
    AdminUserDetail,
    AdminUserListItem,
    AdminUserListResponse,
    AdminUserSort,
    SortOrder,
)
from auth.utils.account_purge import AccountPurgeError, purge_auth_user
from auth.models.user import AuthUser
from auth.utils.invites import connect_signup_inviter, count_signup_invites
from auth.utils.registration import is_registration_complete, pending_signup_reason
from config.constants import AppRole, ConnectionStatus, UserStatus
from core.models.connection import CoreProfileConnection
from core.models.profile import CoreProfile
from core.models.user_role import CoreUserRole
from core.utils.connections import get_connection_between
from core.utils.roles import can_invite_to_platform, load_user_roles

_MULTI_SPACE_RE = re.compile(r"\s+")


def _admin_user_ordering(sort: AdminUserSort, order: SortOrder):
    """Nome, cognome, email o data di iscrizione, con id come spareggio stabile."""
    if sort == AdminUserSort.EMAIL:
        expr = func.lower(AuthUser.email)
    elif sort == AdminUserSort.FIRST_NAME:
        expr = func.lower(func.nullif(func.trim(CoreProfile.first_name), ""))
    elif sort == AdminUserSort.LAST_NAME:
        expr = func.lower(func.nullif(func.trim(CoreProfile.last_name), ""))
    else:
        expr = AuthUser.created_at
    primary = expr.desc() if order == SortOrder.DESC else expr.asc()
    if sort in (AdminUserSort.FIRST_NAME, AdminUserSort.LAST_NAME):
        primary = primary.nulls_last()
    return primary, AuthUser.id.asc()


def list_admin_users(
    db: Session,
    *,
    query: str | None,
    status: UserStatus | None,
    role: AppRole | None,
    invited_only: bool,
    limit: int,
    offset: int,
    include_pending_reason: bool = False,
    sort: AdminUserSort = AdminUserSort.CREATED_AT,
    order: SortOrder = SortOrder.DESC,
) -> AdminUserListResponse:
    """Elenco utenti con filtri staff (nessuna visibility di rete)."""
    filters = [AuthUser.status != UserStatus.DELETED]
    if status == UserStatus.DELETED:
        return AdminUserListResponse(items=[], total=0, limit=limit, offset=offset)
    if status is not None:
        filters.append(AuthUser.status == status)
    if invited_only:
        filters.append(AuthUser.invited_by_id.is_not(None))
    if query:
        pattern = f"%{_escape_like(_normalize_query(query))}%"
        full_name = func.concat(CoreProfile.first_name, " ", CoreProfile.last_name)
        filters.append(
            or_(
                AuthUser.username.ilike(pattern, escape="\\"),
                AuthUser.email.ilike(pattern, escape="\\"),
                CoreProfile.first_name.ilike(pattern, escape="\\"),
                CoreProfile.last_name.ilike(pattern, escape="\\"),
                full_name.ilike(pattern, escape="\\"),
            )
        )

    base = select(AuthUser, CoreProfile).outerjoin(CoreProfile, CoreProfile.user_id == AuthUser.id)
    if role is not None:
        base = base.join(CoreUserRole, CoreUserRole.user_id == AuthUser.id).where(CoreUserRole.role == role)
    if filters:
        base = base.where(*filters)

    count_stmt = select(func.count()).select_from(base.order_by(None).subquery())
    total = int(db.scalar(count_stmt) or 0)
    rows = db.execute(
        base.order_by(*_admin_user_ordering(sort, order)).limit(limit).offset(offset)
    ).all()

    user_ids = [user.id for user, _profile in rows]
    roles_by_user = _load_roles_map(db, user_ids)
    invites_by_user = _load_invites_map(db, user_ids)
    connections_by_user = _load_accepted_connection_counts(db, user_ids)

    items = [
        AdminUserListItem(
            id=user.id,
            username=str(user.username),
            email=str(user.email),
            status=user.status.value,
            roles=roles_by_user.get(user.id, []),
            first_name=profile.first_name if profile is not None else None,
            last_name=profile.last_name if profile is not None else None,
            avatar_url=profile.avatar_url if profile is not None else None,
            created_at=user.created_at,
            invited_by_id=user.invited_by_id,
            invites_count=invites_by_user.get(user.id, 0),
            connections_accepted=connections_by_user.get(user.id, 0),
            pending_reason=pending_signup_reason(user) if include_pending_reason else None,
        )
        for user, profile in rows
    ]
    return AdminUserListResponse(items=items, total=total, limit=limit, offset=offset)


def get_admin_user(db: Session, user_id: uuid.UUID) -> AdminUserDetail:
    """Dettaglio utente + metriche growth/rete/eventi."""
    user = db.get(AuthUser, user_id)
    if user is None or user.status == UserStatus.DELETED:
        raise AdminUserNotFoundError
    profile = db.get(CoreProfile, user_id)
    roles = load_user_roles(db, user_id)
    inviter_username = None
    if user.invited_by_id is not None:
        inviter = db.get(AuthUser, user.invited_by_id)
        inviter_username = str(inviter.username) if inviter is not None else None

    pair_filter = or_(
        CoreProfileConnection.user_low_id == user_id,
        CoreProfileConnection.user_high_id == user_id,
    )
    accepted = int(
        db.scalar(
            select(func.count())
            .select_from(CoreProfileConnection)
            .where(pair_filter, CoreProfileConnection.status == ConnectionStatus.ACCEPTED)
        )
        or 0
    )

    return AdminUserDetail(
        id=user.id,
        username=str(user.username),
        email=str(user.email),
        status=user.status.value,
        roles=roles,
        first_name=profile.first_name if profile is not None else None,
        last_name=profile.last_name if profile is not None else None,
        avatar_url=profile.avatar_url if profile is not None else None,
        created_at=user.created_at,
        invited_by_id=user.invited_by_id,
        invites_count=count_signup_invites(db, user.id),
        connections_accepted=accepted,
        email_verified_at=user.email_verified_at,
        registration_complete=is_registration_complete(db, user.id),
        pending_reason=pending_signup_reason(user),
        invited_by_username=inviter_username,
    )


def update_admin_user(
    db: Session,
    *,
    actor: AuthUser,
    user_id: uuid.UUID,
    status: UserStatus | None,
    roles: list[AppRole] | None,
) -> AdminUserDetail:
    """Aggiorna stato e/o ruoli. Non consente self-lockout né rimuovere l'ultimo super_admin."""
    user = db.get(AuthUser, user_id)
    if user is None:
        raise AdminUserNotFoundError

    if status is not None:
        if status == UserStatus.DELETED:
            raise AdminForbiddenMutationError("Deleted accounts are removed from the database")
        if actor.id == user.id and status == UserStatus.SUSPENDED:
            raise AdminForbiddenMutationError("You cannot suspend your own account")
        user.status = status
        db.add(user)

    if roles is not None:
        unique_roles = list(dict.fromkeys(roles))
        if not unique_roles:
            raise AdminInvalidRolesError
        current = set(load_user_roles(db, user_id))
        next_roles = {role.value for role in unique_roles}
        if (
            AppRole.SUPER_ADMIN.value in current
            and AppRole.SUPER_ADMIN.value not in next_roles
            and _count_super_admins(db, exclude_user_id=user_id) == 0
        ):
            raise AdminForbiddenMutationError("Cannot remove the last super_admin")
        if actor.id == user.id and AppRole.SUPER_ADMIN.value in current and AppRole.SUPER_ADMIN.value not in next_roles:
            raise AdminForbiddenMutationError("You cannot remove your own super_admin role")
        db.execute(delete(CoreUserRole).where(CoreUserRole.user_id == user_id))
        for role in unique_roles:
            db.add(CoreUserRole(user_id=user_id, role=role))

    from admin.services.audit_log import record_audit
    from config.constants import AuditModule

    record_audit(
        db,
        module=AuditModule.USERS,
        action="user.updated",
        message=f"Account @{user.username} aggiornato da console",
        actor=actor,
        target_type="user",
        target_id=user.id,
        payload={
            "username": str(user.username),
            "status": status.value if status is not None else None,
            "roles": [role.value for role in roles] if roles is not None else None,
        },
    )
    db.commit()
    return get_admin_user(db, user_id)


def link_signup_invitee(
    db: Session,
    *,
    actor: AuthUser,
    inviter_id: uuid.UUID,
    invitee_id: uuid.UUID,
) -> AdminUserDetail:
    """Attribuisce l'invito signup e crea la connessione ``accepted``, come il link ``?ref=``."""
    if inviter_id == invitee_id:
        raise AdminForbiddenMutationError("Non puoi collegare un utente a se stesso")

    inviter = db.get(AuthUser, inviter_id)
    if inviter is None or inviter.status == UserStatus.DELETED:
        raise AdminUserNotFoundError("Invitante non trovato")
    if inviter.status != UserStatus.ACTIVE:
        raise AdminForbiddenMutationError("L'invitante deve essere un account attivo")
    if not can_invite_to_platform(load_user_roles(db, inviter_id)):
        raise AdminForbiddenMutationError(
            "L'invitante non può inviare link di iscrizione (serve ruolo ambassador o superiore)"
        )

    invitee = db.get(AuthUser, invitee_id)
    if invitee is None or invitee.status == UserStatus.DELETED:
        raise AdminUserNotFoundError("Utente da collegare non trovato")

    if invitee.invited_by_id is not None and invitee.invited_by_id != inviter_id:
        raise AdminForbiddenMutationError("Questo utente risulta già invitato da un altro account")

    existing = get_connection_between(db, inviter_id, invitee_id)
    if existing is not None and existing.status == ConnectionStatus.BLOCKED:
        raise AdminForbiddenMutationError("Non è possibile collegarli: esiste una relazione bloccata")

    invitee.invited_by_id = inviter_id
    db.add(invitee)
    connect_signup_inviter(db, invitee)

    from admin.services.audit_log import record_audit
    from config.constants import AuditModule

    record_audit(
        db,
        module=AuditModule.USERS,
        action="user.invite_linked",
        message=f"@{invitee.username} collegato come invitato da @{inviter.username}",
        actor=actor,
        target_type="user",
        target_id=invitee.id,
        payload={
            "inviter_id": str(inviter.id),
            "inviter_username": str(inviter.username),
            "invitee_id": str(invitee.id),
            "invitee_username": str(invitee.username),
        },
    )
    db.commit()
    return get_admin_user(db, inviter_id)


def delete_admin_user(db: Session, *, actor: AuthUser, user_id: uuid.UUID) -> AdminUserDeletedResponse:
    """Elimina l'account dal DB (self-delete e ultimo super_admin non consentiti)."""
    user = db.get(AuthUser, user_id)
    if user is None or user.status == UserStatus.DELETED:
        raise AdminUserNotFoundError
    if actor.id == user.id:
        raise AdminForbiddenMutationError("You cannot delete your own account")
    roles = set(load_user_roles(db, user_id))
    if AppRole.SUPER_ADMIN.value in roles and _count_super_admins(db, exclude_user_id=user_id) == 0:
        raise AdminForbiddenMutationError("Cannot delete the last super_admin")
    from admin.services.audit_log import record_audit
    from config.constants import AuditLevel, AuditModule

    record_audit(
        db,
        module=AuditModule.USERS,
        action="user.deleted",
        message=f"Account @{user.username} eliminato da console",
        actor=actor,
        target_type="user",
        target_id=user.id,
        level=AuditLevel.WARNING,
        payload={"username": str(user.username), "email": str(user.email)},
    )
    try:
        purge_auth_user(db, user)
        db.commit()
    except AccountPurgeError as exc:
        db.rollback()
        raise AdminForbiddenMutationError(exc.message) from exc
    return AdminUserDeletedResponse(user_id=user_id)


def _count_super_admins(db: Session, *, exclude_user_id: uuid.UUID) -> int:
    return int(
        db.scalar(
            select(func.count())
            .select_from(CoreUserRole)
            .where(
                CoreUserRole.role == AppRole.SUPER_ADMIN,
                CoreUserRole.user_id != exclude_user_id,
            )
        )
        or 0
    )


def _load_roles_map(db: Session, user_ids: list[uuid.UUID]) -> dict[uuid.UUID, list[str]]:
    if not user_ids:
        return {}
    rows = db.execute(
        select(CoreUserRole.user_id, CoreUserRole.role).where(CoreUserRole.user_id.in_(user_ids))
    ).all()
    mapped: dict[uuid.UUID, list[str]] = {user_id: [] for user_id in user_ids}
    for user_id, role in rows:
        mapped.setdefault(user_id, []).append(role.value)
    return mapped


def _load_invites_map(db: Session, user_ids: list[uuid.UUID]) -> dict[uuid.UUID, int]:
    if not user_ids:
        return {}
    rows = db.execute(
        select(AuthUser.invited_by_id, func.count())
        .where(
            AuthUser.invited_by_id.in_(user_ids),
            AuthUser.status != UserStatus.DELETED,
        )
        .group_by(AuthUser.invited_by_id)
    ).all()
    return {inviter_id: int(count) for inviter_id, count in rows}


def _load_accepted_connection_counts(db: Session, user_ids: list[uuid.UUID]) -> dict[uuid.UUID, int]:
    if not user_ids:
        return {}
    low = (
        select(CoreProfileConnection.user_low_id.label("uid"))
        .where(
            CoreProfileConnection.user_low_id.in_(user_ids),
            CoreProfileConnection.status == ConnectionStatus.ACCEPTED,
        )
    )
    high = (
        select(CoreProfileConnection.user_high_id.label("uid"))
        .where(
            CoreProfileConnection.user_high_id.in_(user_ids),
            CoreProfileConnection.status == ConnectionStatus.ACCEPTED,
        )
    )
    unioned = low.union_all(high).subquery()
    rows = db.execute(select(unioned.c.uid, func.count()).group_by(unioned.c.uid)).all()
    return {user_id: int(count) for user_id, count in rows}


def _normalize_query(raw: str) -> str:
    return _MULTI_SPACE_RE.sub(" ", raw.strip())


def _escape_like(value: str) -> str:
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
