import uuid

from sqlalchemy import Column, DateTime, Enum, ForeignKey, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func

from config.constants import AppRole
from config.db import Base


class CoreUserRole(Base):
    """Tabella ``core_user_roles``: ruoli applicativi multipli per utente."""

    __tablename__ = "core_user_roles"
    __table_args__ = (
        UniqueConstraint("user_id", "role", name="uq_core_user_roles_user_role"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("auth_users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    role = Column(
        Enum(
            AppRole,
            name="app_role",
            values_callable=lambda obj: [m.value for m in obj],
        ),
        nullable=False,
    )
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
