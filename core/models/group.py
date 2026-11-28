"""Gruppo attorno a una prenotazione: membri e inviti tra professional."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, Column, DateTime, Enum, ForeignKey, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func

from config.constants import GroupInviteStatus, GroupMemberRole, GroupStatus
from config.db import Base


class CoreGroup(Base):
    """Tavolo condiviso. Esiste solo se la prenotazione è ``party_kind=group``."""

    __tablename__ = "core_groups"
    __table_args__ = (
        UniqueConstraint("booking_id", name="uq_core_groups_booking"),
        UniqueConstraint("share_code", name="uq_core_groups_share_code"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    booking_id = Column(
        UUID(as_uuid=True),
        ForeignKey("core_bookings.id", ondelete="CASCADE"),
        nullable=False,
    )
    host_user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("auth_users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    title = Column(Text, nullable=True)
    share_code = Column(Text, nullable=True)
    status = Column(
        Enum(
            GroupStatus,
            name="group_status",
            values_callable=lambda obj: [m.value for m in obj],
        ),
        nullable=False,
        default=GroupStatus.OPEN,
    )

    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    @property
    def is_open(self) -> bool:
        return self.status == GroupStatus.OPEN

    def lock(self) -> None:
        """Chiude le adesioni: il roster non cambia più."""
        self.status = GroupStatus.LOCKED

    def close(self) -> None:
        self.status = GroupStatus.CLOSED


class CoreGroupMember(Base):
    """Professional che ha un posto nel gruppo. L'host è una riga con ruolo ``host``."""

    __tablename__ = "core_group_members"
    __table_args__ = (
        UniqueConstraint("group_id", "user_id", name="uq_core_group_members_group_user"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    group_id = Column(
        UUID(as_uuid=True),
        ForeignKey("core_groups.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("auth_users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    role = Column(
        Enum(
            GroupMemberRole,
            name="group_member_role",
            values_callable=lambda obj: [m.value for m in obj],
        ),
        nullable=False,
    )
    joined_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    @property
    def is_host(self) -> bool:
        return self.role == GroupMemberRole.HOST


class CoreGroupInvite(Base):
    """Invito di un professional a entrare nel gruppo. Una riga per destinatario."""

    __tablename__ = "core_group_invites"
    __table_args__ = (
        UniqueConstraint("group_id", "invitee_id", name="uq_core_group_invites_group_invitee"),
        UniqueConstraint("token", name="uq_core_group_invites_token"),
        CheckConstraint(
            "invitee_id IS NOT NULL OR invitee_email IS NOT NULL",
            name="ck_core_group_invites_has_target",
        ),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    group_id = Column(
        UUID(as_uuid=True),
        ForeignKey("core_groups.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    inviter_id = Column(
        UUID(as_uuid=True),
        ForeignKey("auth_users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    invitee_id = Column(
        UUID(as_uuid=True),
        ForeignKey("auth_users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    invitee_email = Column(Text, nullable=True)
    token = Column(Text, nullable=True)
    status = Column(
        Enum(
            GroupInviteStatus,
            name="group_invite_status",
            values_callable=lambda obj: [m.value for m in obj],
        ),
        nullable=False,
        default=GroupInviteStatus.PENDING,
    )

    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    responded_at = Column(DateTime(timezone=True), nullable=True)

    @property
    def is_pending(self) -> bool:
        return self.status == GroupInviteStatus.PENDING

    def _answer(self, status: GroupInviteStatus, when: datetime) -> None:
        self.status = status
        self.responded_at = when

    def accept(self, when: datetime) -> None:
        self._answer(GroupInviteStatus.ACCEPTED, when)

    def decline(self, when: datetime) -> None:
        self._answer(GroupInviteStatus.DECLINED, when)

    def revoke(self, when: datetime) -> None:
        self._answer(GroupInviteStatus.REVOKED, when)