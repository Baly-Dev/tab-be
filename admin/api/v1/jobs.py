"""Job automatici — solo super_admin."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from admin.errors import AdminServiceError, http_error_admin_internal, http_error_from_admin
from admin.schemas.jobs import AdminBatchJobItem, AdminBatchJobListResponse, UpdateAdminBatchJobRequest
from admin.services.batch_jobs import list_batch_jobs, run_batch_job_now, update_batch_job
from config.db.session import get_db
from core.dependencies import SuperAdminUser

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("", response_model=AdminBatchJobListResponse, summary="Job automatici")
def get_admin_batch_jobs(
    _actor: SuperAdminUser,
    db: Session = Depends(get_db),
) -> AdminBatchJobListResponse:
    """Stato, parametri e ultime esecuzioni. Solo super admin."""
    try:
        return list_batch_jobs(db)
    except SQLAlchemyError as exc:
        logger.exception("admin.batch_jobs.list_failed")
        raise http_error_admin_internal("Unable to load batch jobs") from exc


@router.patch("/{job_key}", response_model=AdminBatchJobItem, summary="Aggiorna un job")
def patch_admin_batch_job(
    job_key: str,
    body: UpdateAdminBatchJobRequest,
    actor: SuperAdminUser,
    db: Session = Depends(get_db),
) -> AdminBatchJobItem:
    """Attiva, disattiva o riconfigura intervallo e parametri."""
    try:
        return update_batch_job(db, job_key, body, actor=actor)
    except AdminServiceError as exc:
        raise http_error_from_admin(exc) from exc
    except SQLAlchemyError as exc:
        logger.exception("admin.batch_jobs.update_failed key=%s", job_key)
        raise http_error_admin_internal("Unable to update batch job") from exc


@router.post("/{job_key}/run", response_model=AdminBatchJobItem, summary="Esegui un job")
def post_admin_batch_job_run(
    job_key: str,
    actor: SuperAdminUser,
    db: Session = Depends(get_db),
) -> AdminBatchJobItem:
    """Un ciclo immediato, anche se il job è disattivato."""
    try:
        return run_batch_job_now(db, job_key, actor=actor)
    except AdminServiceError as exc:
        raise http_error_from_admin(exc) from exc
    except SQLAlchemyError as exc:
        logger.exception("admin.batch_jobs.run_failed key=%s", job_key)
        raise http_error_admin_internal("Unable to run batch job") from exc
