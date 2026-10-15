"""Paginated generated-image galleries, scoped to a project or the whole library."""
from typing import Literal

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Asset, GenerationJob, JobStatus, Project
from app.routes.projects import get_project_or_404

router = APIRouter(prefix="/api/gallery", tags=["gallery"])


@router.get("")
def list_gallery(
    project_id: str | None = None,
    purpose: Literal["master", "turnaround", "concept", "enhance", "test"] | None = None,
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=48, ge=1, le=100),
    db: Session = Depends(get_db),
):
    if project_id:
        get_project_or_404(db, project_id)
    query = (db.query(Asset, GenerationJob, Project)
             .join(GenerationJob, Asset.job_id == GenerationJob.id)
             .join(Project, Asset.project_id == Project.id)
             .filter(Asset.kind == "generated", GenerationJob.status == JobStatus.SUCCEEDED,
                     GenerationJob.project_id == Asset.project_id))
    if project_id:
        query = query.filter(Asset.project_id == project_id)
    if purpose:
        query = query.filter(GenerationJob.purpose == purpose)
    total = query.count()
    rows = query.order_by(Asset.created_at.desc(), Asset.id.desc()).offset(offset).limit(limit).all()
    return {"total": total, "items": [
        {"id": asset.id, "project_id": project.id, "project_name": project.name,
         "purpose": job.purpose, "provider": job.provider, "model": job.model,
         "prompt": job.prompt, "filename": asset.filename, "created_at": asset.created_at,
         "width": asset.width, "height": asset.height, "meta": job.meta or {}}
        for asset, job, project in rows
    ]}
