"""Lettura, aggiornamento ed esecuzione dei job automatici."""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from admin.errors import AdminBatchJobConfigError, AdminBatchJobNotFoundError
from admin.models.batch_job import BatchJob, BatchJobRun
from admin.schemas.jobs import (
    AdminBatchJobField,
    AdminBatchJobItem,
    AdminBatchJobListResponse,
    AdminBatchJobRunItem,
    UpdateAdminBatchJobRequest,
)
from admin.services.audit_log import record_audit
from admin.services.batch_job_catalog import (
    JOBS,
    JOBS_BY_KEY,
    RUN_HISTORY_LIMIT,
    JobConfigError,
    JobSpec,
    config_int,
    default_config,
    normalize_config,
    normalize_interval,
)
from auth.models.user import AuthUser
from config.constants import AuditModule

logger = logging.getLogger(__name__)

_RECENT_RUNS = 8


def list_batch_jobs(db: Session) -> AdminBatchJobListResponse:
    """Catalogo con stato corrente e ultime esecuzioni rilevanti."""
    rows = {row.key: row for row in _ensure_rows(db)}
    db.commit()
    return AdminBatchJobListResponse(
        jobs=[_to_item(db, JOBS_BY_KEY[key], rows[key]) for key in (spec.key for spec in JOBS)]
    )


def update_batch_job(
    db: Session,
    key: str,
    body: UpdateAdminBatchJobRequest,
    *,
    actor: AuthUser,
) -> AdminBatchJobItem:
    """Attiva, disattiva o cambia intervallo e parametri."""
    spec = _spec_or_raise(key)
    row = _row_or_raise(db, spec)
    try:
        interval = normalize_interval(body.interval_seconds)
        config = normalize_config(spec, body.config)
    except JobConfigError as exc:
        raise AdminBatchJobConfigError(str(exc)) from exc
    row.enabled = body.enabled
    row.interval_seconds = interval
    row.config = config
    row.updated_at = datetime.now(UTC)
    row.updated_by = actor.id
    record_audit(
        db,
        module=AuditModule.ADMIN,
        action="batch_job.updated",
        message=f"Job «{spec.title}» aggiornato",
        actor=actor,
        target_type="batch_job",
        target_id=spec.key,
        payload={"enabled": body.enabled, "interval_seconds": interval, "config": config},
    )
    db.commit()
    db.refresh(row)
    return _to_item(db, spec, row)


def run_batch_job_now(db: Session, key: str, *, actor: AuthUser) -> AdminBatchJobItem:
    """Esegue un ciclo subito, anche se il job è disattivato."""
    spec = _spec_or_raise(key)
    row = _row_or_raise(db, spec)
    _execute(db, row, trigger="manual", actor=actor)
    db.refresh(row)
    return _to_item(db, spec, row)


def run_due_jobs(db: Session) -> int:
    """Esegue i job attivi il cui intervallo è scaduto. Ritorna i secondi di attesa."""
    now = datetime.now(UTC)
    rows = _ensure_rows(db)
    db.commit()
    for row in rows:
        if not row.enabled:
            continue
        if row.last_started_at is not None:
            due_at = row.last_started_at + timedelta(seconds=int(row.interval_seconds))
            if due_at > now:
                continue
        _execute(db, row, trigger="schedule", actor=None)
    enabled = [int(row.interval_seconds) for row in rows if row.enabled]
    if not enabled:
        return 300
    return max(60, min(enabled))


def _execute(
    db: Session,
    row: BatchJob,
    *,
    trigger: str,
    actor: AuthUser | None,
) -> None:
    spec = JOBS_BY_KEY[str(row.key)]
    started = datetime.now(UTC)
    try:
        sent = _dispatch(db, spec, row.config if isinstance(row.config, dict) else {})
        db.refresh(row)
    except Exception as exc:
        logger.exception("batch_job.failed key=%s", row.key)
        db.rollback()
        failed = db.get(BatchJob, spec.key)
        if failed is None:
            return
        finished = datetime.now(UTC)
        message = "Esecuzione fallita."
        error = str(exc)[:500]
        failed.last_started_at = started
        failed.last_finished_at = finished
        failed.last_status = "error"
        failed.last_sent_count = 0
        failed.last_error = error
        db.add(
            _run_row(
                spec.key,
                started=started,
                finished=finished,
                status="error",
                sent_count=0,
                trigger=trigger,
                message=message,
                error=error,
                actor=actor,
            )
        )
        _trim_runs(db, spec.key)
        db.commit()
        return

    finished = datetime.now(UTC)
    message = _sent_message(sent)
    row.last_started_at = started
    row.last_finished_at = finished
    row.last_status = "ok"
    row.last_sent_count = sent
    row.last_error = None
    if sent > 0 or trigger == "manual":
        db.add(
            _run_row(
                spec.key,
                started=started,
                finished=finished,
                status="ok",
                sent_count=sent,
                trigger=trigger,
                message=message,
                error=None,
                actor=actor,
            )
        )
        _trim_runs(db, spec.key)
    if trigger == "manual" and actor is not None:
        record_audit(
            db,
            module=AuditModule.ADMIN,
            action="batch_job.ran",
            message=f"Job «{spec.title}» eseguito: {message}",
            actor=actor,
            target_type="batch_job",
            target_id=spec.key,
            payload={"sent_count": sent},
        )
    db.commit()


def _dispatch(db: Session, spec: JobSpec, config: dict) -> int:
    """Nessun job di dominio è registrato in questa base."""
    _ = db, config
    raise AdminBatchJobNotFoundError(f"Job non disponibile: {spec.key}")


def _ensure_rows(db: Session) -> list[BatchJob]:
    existing = {row.key: row for row in db.scalars(select(BatchJob)).all()}
    created = False
    for spec in JOBS:
        if spec.key in existing:
            continue
        row = BatchJob(
            key=spec.key,
            enabled=True,
            interval_seconds=spec.default_interval_seconds,
            config=default_config(spec),
            updated_at=datetime.now(UTC),
        )
        db.add(row)
        existing[spec.key] = row
        created = True
    if created:
        db.flush()
    return [existing[spec.key] for spec in JOBS]


def _spec_or_raise(key: str) -> JobSpec:
    spec = JOBS_BY_KEY.get(key)
    if spec is None:
        raise AdminBatchJobNotFoundError()
    return spec


def _row_or_raise(db: Session, spec: JobSpec) -> BatchJob:
    rows = {row.key: row for row in _ensure_rows(db)}
    return rows[spec.key]


def _to_item(db: Session, spec: JobSpec, row: BatchJob) -> AdminBatchJobItem:
    stored = row.config if isinstance(row.config, dict) else {}
    fields = [
        AdminBatchJobField(
            key=field.key,
            label=field.label,
            help=field.help,
            minimum=field.minimum,
            maximum=field.maximum,
            value=config_int(stored, field.key, field.default),
        )
        for field in spec.fields
    ]
    runs = db.scalars(
        select(BatchJobRun)
        .where(BatchJobRun.job_key == spec.key)
        .order_by(BatchJobRun.started_at.desc())
        .limit(_RECENT_RUNS)
    ).all()
    return AdminBatchJobItem(
        key=spec.key,
        title=spec.title,
        description=spec.description,
        enabled=bool(row.enabled),
        interval_seconds=int(row.interval_seconds),
        fields=fields,
        last_started_at=row.last_started_at,
        last_finished_at=row.last_finished_at,
        last_status=row.last_status,
        last_sent_count=row.last_sent_count,
        last_error=row.last_error,
        runs=[
            AdminBatchJobRunItem(
                id=run.id,
                started_at=run.started_at,
                finished_at=run.finished_at,
                status=str(run.status),
                sent_count=int(run.sent_count),
                trigger=str(run.trigger),
                message=str(run.message),
                error=run.error,
                actor_username=run.actor_username,
            )
            for run in runs
        ],
    )


def _run_row(
    job_key: str,
    *,
    started: datetime,
    finished: datetime,
    status: str,
    sent_count: int,
    trigger: str,
    message: str,
    error: str | None,
    actor: AuthUser | None,
) -> BatchJobRun:
    return BatchJobRun(
        job_key=job_key,
        started_at=started,
        finished_at=finished,
        status=status,
        sent_count=sent_count,
        trigger=trigger,
        message=message,
        error=error,
        actor_username=str(actor.username) if actor is not None else None,
    )


def _trim_runs(db: Session, job_key: str) -> None:
    stale_ids = db.scalars(
        select(BatchJobRun.id)
        .where(BatchJobRun.job_key == job_key)
        .order_by(BatchJobRun.started_at.desc())
        .offset(RUN_HISTORY_LIMIT)
    ).all()
    if stale_ids:
        db.execute(delete(BatchJobRun).where(BatchJobRun.id.in_(stale_ids)))


def _sent_message(sent: int) -> str:
    if sent == 0:
        return "Nessun invio."
    if sent == 1:
        return "1 invio."
    return f"{sent} invii."
