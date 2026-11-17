"""Soft deletion never removes job history, costs, or generated files."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Asset, GenerationJob, JobStatus, MasterVersion, Project, TurnaroundVersion
from app.routes.assets import _asset, storage
from app.routes.jobs import _job_or_404

router = APIRouter(prefix="/api/trash", tags=["trash"])


def fail(message):
    raise HTTPException(409, detail={"code": "trash_conflict", "message": message})


def generated(db, asset_id):
    asset = _asset(db, asset_id)
    if asset.kind != "generated":
        fail("Chỉ chuyển ảnh đã tạo vào Thùng rác ở đây.")
    return asset


def protect_outputs(db, assets):
    ids = {a.id for a in assets}
    if not ids:
        return
    for job in db.query(GenerationJob).filter(GenerationJob.purged.is_(False)):
        if ids.intersection(job.reference_asset_ids or []):
            fail("Ảnh đang được dùng làm tham chiếu. Giữ trong Thùng rác để không mất dữ liệu liên quan.")
    for project in db.query(Project):
        master = db.get(MasterVersion, project.approved_master_id) if project.approved_master_id else None
        if master and ids.intersection(master.job.output_asset_ids):
            fail("Ảnh là nhân vật gốc đã duyệt. Hãy duyệt phiên bản khác trước khi xoá vĩnh viễn.")
        turn = db.get(TurnaroundVersion, project.approved_turnaround_id) if project.approved_turnaround_id else None
        if turn and any(ids.intersection(v.job.output_asset_ids) for v in turn.views if v.selected):
            fail("Ảnh thuộc turnaround đã duyệt. Hãy duyệt phiên bản khác trước khi xoá vĩnh viễn.")


@router.get("")
def list_trash(db: Session = Depends(get_db)):
    rows = []
    for job, name in db.query(GenerationJob, Project.name).join(Project).filter(GenerationJob.dismissed.is_(True), GenerationJob.purged.is_(False)):
        rows.append({"kind": "job", "id": job.id, "project_id": job.project_id, "project_name": name,
                     "title": f"{job.purpose} · {job.status}", "error_message": job.error_message,
                     "asset_ids": job.output_asset_ids, "created_at": job.created_at})
    for asset, name in db.query(Asset, Project.name).join(Project).filter(Asset.trashed.is_(True)):
        # A run owns its outputs in trash; individual flags survive restoring the run.
        job = db.get(GenerationJob, asset.job_id) if asset.job_id else None
        if job and job.dismissed:
            continue
        rows.append({"kind": "asset", "id": asset.id, "project_id": asset.project_id, "project_name": name,
                     "title": asset.filename, "error_message": None, "asset_ids": [asset.id], "created_at": asset.created_at})
    return sorted(rows, key=lambda r: (r["created_at"], r["id"]), reverse=True)


@router.post("/assets/{asset_id}")
def trash_asset(asset_id: str, db: Session = Depends(get_db)):
    asset = generated(db, asset_id)
    if asset.job_id and db.get(GenerationJob, asset.job_id).status not in JobStatus.FINAL:
        fail("Hãy chờ lượt tạo hoàn tất.")
    asset.trashed = True
    db.commit()
    return {"trashed": True}


@router.post("/{kind}/{item_id}/restore")
def restore(kind: str, item_id: str, db: Session = Depends(get_db)):
    if kind == "asset":
        asset = generated(db, item_id)
        job = db.get(GenerationJob, asset.job_id) if asset.job_id else None
        if job and job.dismissed:
            fail("Khôi phục run trước khi khôi phục riêng ảnh.")
        asset.trashed = False
    elif kind == "job":
        job = _job_or_404(db, item_id)
        if job.purged:
            fail("Run đã xoá vĩnh viễn, không thể khôi phục.")
        job.dismissed = False
    else:
        raise HTTPException(404)
    db.commit()
    return {"restored": True}


@router.delete("/{kind}/{item_id}")
def purge(kind: str, item_id: str, db: Session = Depends(get_db)):
    job = None
    if kind == "asset":
        asset = generated(db, item_id)
        if not asset.trashed:
            fail("Chuyển ảnh vào Thùng rác trước khi xoá vĩnh viễn.")
        assets = [asset]
    elif kind == "job":
        job = _job_or_404(db, item_id)
        if not job.dismissed or job.purged or job.status not in JobStatus.FINAL:
            fail("Run phải nằm trong Thùng rác trước khi xoá vĩnh viễn.")
        assets = db.query(Asset).filter(Asset.job_id == job.id).all()
    else:
        raise HTTPException(404)
    protect_outputs(db, assets)
    ids = {a.id for a in assets}
    paths = [a.file_path for a in assets]
    for owner in db.query(GenerationJob):
        if ids.intersection(owner.output_asset_ids):
            owner.output_asset_ids = [i for i in owner.output_asset_ids if i not in ids]
    for asset in assets:
        db.delete(asset)
    if job:
        # Preserve run identity, domain links, and cost totals; remove it from trash permanently.
        job.purged = True
        job.prompt = ""
        job.reference_asset_ids = []
        job.error_message = None
    db.commit()
    for path in paths:
        storage.delete(path)
    return {"deleted": True}
