from __future__ import annotations

import uuid

from sqlalchemy import CheckConstraint, Column, DateTime, Enum, ForeignKey, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func

from config.constants import ConnectionStatus
from config.db import Base


class CoreProfileConnection(Base):
    """Tabella `core_profile_connections`: relazione 1° grado tra due `auth_users.id`."""

    __tablename__ = "core_profile_connections"

    __table_args__ = (
        CheckConstraint(
            "user_low_id < user_high_id",
            name="ck_core_profile_connections_user_pair_order",
        ),
        CheckConstraint(
            "initiated_by_id = user_low_id OR initiated_by_id = user_high_id",
            name="ck_core_profile_connections_initiated_by_pair_member",
        ),
        UniqueConstraint(
            "user_low_id",
            "user_high_id",
            name="uq_core_profile_connections_user_pair",
        ),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_low_id = Column(
        UUID(as_uuid=True),
        ForeignKey("auth_users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_high_id = Column(
        UUID(as_uuid=True),
        ForeignKey("auth_users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    status = Column(
        Enum(
            ConnectionStatus,
            name="connection_status",
            values_callable=lambda obj: [m.value for m in obj],
        ),
        nullable=False,
        index=True,
    )
    initiated_by_id = Column(
        UUID(as_uuid=True),
        ForeignKey("auth_users.id", ondelete="CASCADE"),
        nullable=False,
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
    def is_accepted(self) -> bool:
        return self.status == ConnectionStatus.ACCEPTED

    @property
    def is_pending(self) -> bool:
        return self.status == ConnectionStatus.PENDING

    @property
    def is_blocked(self) -> bool:
        return self.status == ConnectionStatus.BLOCKED

    def involves_user(self, user_id: uuid.UUID) -> bool:
        return user_id in {self.user_low_id, self.user_high_id}

    def peer_user_id(self, viewer_id: uuid.UUID) -> uuid.UUID:
        """Id dell'altro utente nella coppia canonica."""
        if self.user_low_id == viewer_id:
            return self.user_high_id
        if self.user_high_id == viewer_id:
            return self.user_low_id
        msg = "viewer_id must be a member of the connection pair"
        raise ValueError(msg)

    def initiated_by_viewer(self, viewer_id: uuid.UUID) -> bool:
        return self.initiated_by_id == viewer_id

    @staticmethod
    def ordered_user_pair(
        user_id_a: uuid.UUID,
        user_id_b: uuid.UUID,
    ) -> tuple[uuid.UUID, uuid.UUID]:
        """`(user_low_id, user_high_id)` con UUID ordinati."""
        if user_id_a == user_id_b:
            msg = "core_profile_connections: servono due utenti distinti"
            raise ValueError(msg)
        if user_id_a < user_id_b:
            return user_id_a, user_id_b
        return user_id_b, user_id_a