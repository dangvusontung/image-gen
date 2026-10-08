from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.orm import Session

from app.database import get_db
from app.jobs.service import JobRequestError, request_cancel, retry_job
from app.models import GenerationJob
from app.providers.registry import ProviderRegistry, get_registry
from app.routes.projects import get_project_or_404
from app.schemas import JobOut

router = APIRouter(tags=["jobs"])


def notify_runner(request: Request) -> None:
    runner = getattr(request.app.state, "runner", None)
    if runner is not None:
        runner.notify()


def _job_or_404(db: Session, job_id: str) -> GenerationJob:
    job = db.get(GenerationJob, job_id)
    if job is None:
        raise HTTPException(404, detail={"code": "job_not_found", "message": "Không tìm thấy job"})
    return job


def _raise(exc: JobRequestError):
    raise HTTPException(exc.status, detail={"code": exc.code, "message": exc.message})


@router.get("/api/projects/{project_id}/jobs", response_model=list[JobOut])
def list_jobs(
    project_id: str,
    status: Optional[str] = None,
    purpose: Optional[str] = None,
    limit: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db),
):
    get_project_or_404(db, project_id)
    query = db.query(GenerationJob).filter(GenerationJob.project_id == project_id)
    if status:
        query = query.filter(GenerationJob.status.in_(status.split(",")))
    if purpose:
        query = query.filter(GenerationJob.purpose == purpose)
    return query.order_by(GenerationJob.created_at.desc()).limit(limit).all()


@router.get("/api/jobs/{job_id}", response_model=JobOut)
def get_job(job_id: str, db: Session = Depends(get_db)):
    return _job_or_404(db, job_id)


@router.post("/api/jobs/{job_id}/cancel", response_model=JobOut)
def cancel_job(job_id: str, request: Request, db: Session = Depends(get_db)):
    job = _job_or_404(db, job_id)
    try:
        request_cancel(db, job)
    except JobRequestError as exc:
        _raise(exc)
    db.commit()
    db.refresh(job)
    notify_runner(request)
    return job


@router.post("/api/jobs/{job_id}/retry", response_model=JobOut, status_code=201)
def retry(job_id: str, request: Request, db: Session = Depends(get_db), registry: ProviderRegistry = Depends(get_registry)):
    job = _job_or_404(db, job_id)
    try:
        new_job = retry_job(db, registry, job)
    except JobRequestError as exc:
        _raise(exc)
    db.commit()
    db.refresh(new_job)
    notify_runner(request)
    return new_job
