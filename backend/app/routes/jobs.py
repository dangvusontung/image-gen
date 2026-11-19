import asyncio
import json
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import SessionLocal, get_db
from app.jobs.events import job_events_hub
from app.jobs.service import JobRequestError, request_cancel, retry_job
from app.models import GenerationJob, JobStatus, Project, StickerPack
from app.providers.registry import ProviderRegistry, get_registry
from app.routes.projects import get_project_or_404
from app.schemas import JobHistoryOut, JobOut

router = APIRouter(tags=["jobs"])
_JOB_EVENTS_RECHECK_SECONDS = 15


def notify_runner(request: Request) -> None:
    runner = getattr(request.app.state, "runner", None)
    if runner is not None:
        runner.notify()


def _job_or_404(db: Session, job_id: str) -> GenerationJob:
    job = db.get(GenerationJob, job_id)
    if job is None or job.purged:
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
    query = db.query(GenerationJob).filter(GenerationJob.project_id == project_id, GenerationJob.dismissed.is_(False))
    if status:
        query = query.filter(GenerationJob.status.in_(status.split(",")))
    if purpose:
        query = query.filter(GenerationJob.purpose == purpose)
    return query.order_by(GenerationJob.created_at.desc()).limit(limit).all()


@router.get("/api/projects/{project_id}/jobs/events")
def job_events(project_id: str, request: Request, db: Session = Depends(get_db, scope="function")):
    """Stream one event per generation as its job record changes.

    A generation is represented by one GenerationJob.  Sending the whole job
    list made a large batch look like one update to the client and needlessly
    retransmitted every generation whenever one of them changed.
    """
    get_project_or_404(db, project_id)

    def snapshot() -> dict[str, str]:
        with SessionLocal() as session:
            jobs = (session.query(GenerationJob)
                    .filter(GenerationJob.project_id == project_id, GenerationJob.dismissed.is_(False))
                    .order_by(GenerationJob.created_at.desc()).limit(500).all())
            return {job.id: JobOut.model_validate(job).model_dump_json() for job in jobs}

    async def stream():
        last_jobs: dict[str, str] = {}
        initial = True
        heartbeat_at = 0.0
        loop = asyncio.get_running_loop()
        with job_events_hub.subscribe(project_id) as signal:
            while True:
                if await request.is_disconnected():
                    return
                signal.clear()
                current_jobs = await asyncio.to_thread(snapshot)
                now = loop.time()
                changed = [job_id for job_id, value in current_jobs.items()
                           if last_jobs.get(job_id) != value]
                removed = [job_id for job_id in last_jobs if job_id not in current_jobs]
                if initial or changed or removed:
                    for job_id in changed:
                        yield f"event: generation\ndata: {current_jobs[job_id]}\n\n"
                    for job_id in removed:
                        yield f"event: generation_removed\ndata: {json.dumps({'id': job_id})}\n\n"
                    if initial:
                        yield "event: snapshot_end\ndata: {}\n\n"
                        initial = False
                    last_jobs = current_jobs
                    heartbeat_at = now
                elif now - heartbeat_at >= _JOB_EVENTS_RECHECK_SECONDS:
                    yield ": keep-alive\n\n"
                    heartbeat_at = now
                remaining = heartbeat_at + _JOB_EVENTS_RECHECK_SECONDS - loop.time()
                if remaining <= 0:
                    continue
                try:
                    await asyncio.wait_for(signal.wait(), timeout=remaining)
                except TimeoutError:
                    pass

    return StreamingResponse(stream(), media_type="text/event-stream", headers={
        "Cache-Control": "no-cache", "Connection": "keep-alive", "X-Accel-Buffering": "no",
    })


@router.get("/api/jobs", response_model=list[JobHistoryOut])
def list_all_jobs(
    status: Optional[str] = None,
    purpose: Optional[str] = None,
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
):
    """Newest generations across every project, for the global history popup."""
    query = db.query(GenerationJob, Project.name).join(Project, Project.id == GenerationJob.project_id).filter(GenerationJob.dismissed.is_(False))
    if purpose != "sticker":
        query = query.filter(~Project.id.in_(db.query(StickerPack.project_id)))
    if status:
        query = query.filter(GenerationJob.status.in_(status.split(",")))
    if purpose:
        query = query.filter(GenerationJob.purpose == purpose)
    rows = query.order_by(GenerationJob.created_at.desc()).limit(limit).all()
    return [JobHistoryOut(**JobOut.model_validate(job).model_dump(), project_name=name) for job, name in rows]


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


class RetryRequest(BaseModel):
    """Optionally retry on a different provider or model, e.g. after a refusal."""
    provider: Optional[str] = None
    model: Optional[str] = None


@router.post("/api/jobs/{job_id}/retry", response_model=JobOut, status_code=201)
def retry(job_id: str, request: Request, data: RetryRequest | None = None, db: Session = Depends(get_db),
          registry: ProviderRegistry = Depends(get_registry)):
    job = _job_or_404(db, job_id)
    try:
        new_job = retry_job(db, registry, job, data.provider if data else None, data.model if data else None)
    except JobRequestError as exc:
        _raise(exc)
    db.commit()
    db.refresh(new_job)
    notify_runner(request)
    return new_job


@router.delete("/api/jobs/{job_id}")
def trash_job(job_id: str, db: Session = Depends(get_db)):
    job = _job_or_404(db, job_id)
    if job.status not in JobStatus.FINAL:
        raise HTTPException(409, detail={"code": "job_not_removable", "message": "Hãy huỷ hoặc chờ lượt tạo hoàn tất trước khi chuyển vào Thùng rác."})
    job.dismissed = True
    db.commit()
    return {"removed": True}
