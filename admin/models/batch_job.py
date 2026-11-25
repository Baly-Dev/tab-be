"""Stato e storico dei job automatici della console."""

from __future__ import annotations

import uuid

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Index, Integer, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID

from config.db import Base


class BatchJob(Base):
    """Configurazione persistente di un job del catalogo."""

    __tablename__ = "batch_jobs"

    key = Column(Text, primary_key=True)
    enabled = Column(Boolean, nullable=False, default=True, server_default="true")
    interval_seconds = Column(Integer, nullable=False, default=300, server_default="300")
    config = Column(JSONB, nullable=False, default=dict, server_default="{}")
    last_started_at = Column(DateTime(timezone=True), nullable=True)
    last_finished_at = Column(DateTime(timezone=True), nullable=True)
    last_status = Column(Text, nullable=True)
    last_sent_count = Column(Integer, nullable=True)
    last_error = Column(Text, nullable=True)
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_by = Column(
        UUID(as_uuid=True),
        ForeignKey("auth_users.id", ondelete="SET NULL"),
        nullable=True,
    )


class BatchJobRun(Base):
    """Esecuzione con invii, errore, o avvio manuale."""

    __tablename__ = "batch_job_runs"
    __table_args__ = (Index("ix_batch_job_runs_job_started", "job_key", "started_at"),)

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    job_key = Column(Text, ForeignKey("batch_jobs.key", ondelete="CASCADE"), nullable=False)
    started_at = Column(DateTime(timezone=True), nullable=False)
    finished_at = Column(DateTime(timezone=True), nullable=False)
    status = Column(Text, nullable=False)
    sent_count = Column(Integer, nullable=False, default=0, server_default="0")
    trigger = Column(Text, nullable=False)
    message = Column(Text, nullable=False)
    error = Column(Text, nullable=True)
    actor_username = Column(Text, nullable=True)
