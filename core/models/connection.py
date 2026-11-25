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
