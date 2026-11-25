from sqlalchemy import Boolean, Column, Date, DateTime, ForeignKey, SmallInteger, Text, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func

from config.db import Base


class CoreProfile(Base):
    """Tabella `core_profiles`: dati profilo 1:1 con `auth_users` (`user_id` = PK + FK)."""

    __tablename__ = "core_profiles"

    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("auth_users.id", ondelete="CASCADE"),
        primary_key=True,
    )

    first_name = Column(Text, nullable=False)
    last_name = Column(Text, nullable=False)
    birth_date = Column(Date, nullable=True)
    gender = Column(Text, nullable=True)
    marketing_consent = Column(Boolean, nullable=False, default=False, server_default=text("false"))
    residence_country = Column(Text, nullable=True)
    residence_city = Column(Text, nullable=True)
    bio = Column(Text, nullable=True)
    avatar_url = Column(Text, nullable=True)

    current_company_name = Column(Text, nullable=True)
    current_job_position = Column(Text, nullable=True)
    linkedin_url = Column(Text, nullable=True)

    profile_completeness = Column(
        SmallInteger,
        nullable=False,
        server_default=text("0"),
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
