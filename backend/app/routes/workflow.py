"""Versioned master and turnaround workflow; all generation uses persistent jobs."""
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.database import get_db
from app.generation_policy import generation_target
from app.jobs.service import JobRequestError, check_spend, enqueue_job
from app.models import ApprovalEvent, Asset, JobStatus, MasterVersion, TurnaroundVersion, TurnaroundView
from app.prompts import TemplateError, render, resolve, save_override
from app.providers.registry import get_registry
from app.routes.jobs import notify_runner, _raise
from app.routes.projects import get_project_or_404
from app.schemas import GenerationResult, JobOut, PromptOut, WorkflowOut

router = APIRouter(tags=["workflow"])
ANGLES = {
    "front": "front 0°", "left45": "left three-quarter 45°", "left90": "left profile 90°",
    "right45": "right three-quarter 45°", "right90": "right profile 90°", "back": "back 180°",
}


def fail(code, message, status=409):
    raise HTTPException(status, detail={"code": code, "message": message})


class Generate(BaseModel):
    variants: int = Field(default=1, ge=1, le=4)
    confirmed: bool = False


class PromptUpdate(BaseModel):
    body: str | None = Field(default=None, max_length=8000)


def owned(db, cls, project_id, version_id):
    row = db.get(cls, version_id)
    if row is None or row.project_id != project_id:
        fail("version_not_found", "Không tìm thấy phiên bản", 404)
    return row


def output(db, master):
    if master.job.status != JobStatus.SUCCEEDED or not master.job.output_asset_ids:
        fail("master_not_ready", "Nhân vật gốc chưa tạo thành công")
    asset_id = master.job.output_asset_ids[0]
    if db.get(Asset, asset_id) is None:
        fail("output_missing", "Ảnh kết quả không còn tồn tại")
    return asset_id


def snapshot(db, project_id, name, **values):
    template = resolve(db, name, project_id)
    return render(template.body, **values), {
        "template_name": name, "template_version": template.template_version,
        "template_revision": template.revision, "template_body": template.body,
    }


def finish(db, request, jobs, confirmed):
    # Validate the entire batch before commit; a rejected request persists no jobs.
    paid = [j for j in jobs if j.provider != "mock"]
    if len(jobs) > 1 and paid and not confirmed:
        db.rollback()
        fail("bulk_confirmation_required", "Xác nhận chi phí trước khi tạo nhiều ảnh", 400)
    try:
        check_spend(db, sum(j.estimated_cost_usd or 0 for j in paid), exclude_ids=[j.id for j in jobs])
    except JobRequestError as exc:
        db.rollback()
        _raise(exc)
    db.commit()
    notify_runner(request)


def queue(db, registry, project, **kwargs):
    provider_name, model_id, default_size = generation_target(project, kwargs["purpose"])
    kwargs["meta"] = {**(kwargs.get("meta") or {}), "workflow_mode": project.workflow_mode}
    kwargs.setdefault("provider_name", provider_name)
    kwargs.setdefault("model_id", model_id)
    if not kwargs.get("size") and default_size:
        kwargs["size"] = default_size
    try:
        # Batch spend is checked together before commit, without double counting.
        with db.no_autoflush:
            return enqueue_job(db, registry, project, skip_spend_check=True, **kwargs)
    except JobRequestError as exc:
        db.rollback()
        _raise(exc)


@router.get("/api/prompts/{name}", response_model=PromptOut)
def get_prompt(name: str, project_id: str | None = None, db: Session = Depends(get_db)):
    if project_id:
        get_project_or_404(db, project_id)
    try:
        return resolve(db, name, project_id)
    except TemplateError as exc:
        fail(exc.code, exc.message, 400)


@router.put("/api/prompts/{name}", response_model=PromptOut)
def put_prompt(name: str, data: PromptUpdate, project_id: str | None = None, db: Session = Depends(get_db)):
    if project_id:
        get_project_or_404(db, project_id)
    try:
        save_override(db, name, data.body, project_id)
        db.commit()
        return resolve(db, name, project_id)
    except TemplateError as exc:
        fail(exc.code, exc.message, 400)


@router.get("/api/projects/{project_id}/workflow", response_model=WorkflowOut)
def get_workflow(project_id: str, db: Session = Depends(get_db)):
    project = get_project_or_404(db, project_id)
    masters = db.query(MasterVersion).filter_by(project_id=project_id).order_by(MasterVersion.created_at.desc()).all()
    turns = db.query(TurnaroundVersion).filter_by(project_id=project_id).order_by(TurnaroundVersion.number.desc()).all()
    events = db.query(ApprovalEvent).filter_by(project_id=project_id).order_by(ApprovalEvent.created_at.desc()).all()
    return {
        "approved_master_id": project.approved_master_id,
        "approved_turnaround_id": project.approved_turnaround_id,
        "masters": [{"id": m.id, "round": m.round, "variant": m.variant, "job": JobOut.model_validate(m.job)} for m in masters],
        "turnarounds": [{"id": t.id, "number": t.number, "master_version_id": t.master_version_id,
                         "stale": t.master_version_id != project.approved_master_id,
                         "approved_at": t.approved_at,
                         "views": [{"angle": v.angle, "job": JobOut.model_validate(v.job)} for v in t.views if v.selected]} for t in turns],
        "approvals": [{"target_type": e.target_type, "target_id": e.target_id, "previous_id": e.previous_id,
                       "created_at": e.created_at} for e in events],
    }


@router.post("/api/projects/{project_id}/master/generate", response_model=GenerationResult, status_code=201)
def generate_master(project_id: str, data: Generate, request: Request, db: Session = Depends(get_db), registry=Depends(get_registry)):
    project = get_project_or_404(db, project_id)
    refs = db.query(Asset).filter(Asset.project_id == project_id, Asset.kind.in_(["reference", "side_profile"])).order_by(Asset.position).all()
    if not refs:
        fail("references_required", "Tải ít nhất một ảnh tham chiếu", 400)
    prompt, meta = snapshot(db, project_id, "master")
    number = (db.query(func.max(MasterVersion.round)).filter_by(project_id=project_id).scalar() or 0) + 1
    jobs = []
    for variant in range(1, data.variants + 1):
        job = queue(db, registry, project, purpose="master", prompt=prompt, reference_asset_ids=[r.id for r in refs], aspect_ratio="3:4", meta=meta)
        db.flush()
        db.add(MasterVersion(project_id=project_id, job_id=job.id, round=number, variant=variant))
        jobs.append(job)
    finish(db, request, jobs, data.confirmed)
    return {"job_ids": [j.id for j in jobs]}


@router.post("/api/projects/{project_id}/master/{version_id}/approve")
def approve_master(project_id: str, version_id: str, db: Session = Depends(get_db)):
    project = get_project_or_404(db, project_id)
    output(db, owned(db, MasterVersion, project_id, version_id))
    if project.approved_master_id != version_id:
        db.add(ApprovalEvent(project_id=project_id, target_type="master", target_id=version_id, previous_id=project.approved_master_id))
        project.approved_master_id = version_id
        project.approved_turnaround_id = None
        db.commit()
    return {"approved_master_id": version_id}


def create_turn(db, registry, project, previous=None, angle=None):
    if not project.approved_master_id:
        fail("master_required", "Tạo và duyệt nhân vật gốc trước khi tạo turnaround")
    master = owned(db, MasterVersion, project.id, project.approved_master_id)
    master_asset = output(db, master)
    sides = db.query(Asset).filter_by(project_id=project.id, kind="side_profile").order_by(Asset.position).all()
    number = (db.query(func.max(TurnaroundVersion.number)).filter_by(project_id=project.id).scalar() or 0) + 1
    turn = TurnaroundVersion(project_id=project.id, master_version_id=master.id, number=number, forked_from_id=previous.id if previous else None)
    db.add(turn)
    db.flush()
    jobs = []
    for key, label in ANGLES.items():
        if previous and key != angle:
            view = next(v for v in previous.views if v.angle == key and v.selected)
            job = view.job
        else:
            prompt, meta = snapshot(db, project.id, "turnaround", angle=label)
            meta.update(master_version_id=master.id, reference_labels=["MASTER identity authority"] + ["Real side-profile photo" for _ in sides])
            job = queue(db, registry, project, purpose="turnaround", prompt=prompt,
                        reference_asset_ids=[master_asset] + [s.id for s in sides], aspect_ratio="3:4", meta=meta)
            db.flush()
            jobs.append(job)
        db.add(TurnaroundView(turnaround_version_id=turn.id, angle=key, job_id=job.id, selected=True))
    return turn, jobs


@router.post("/api/projects/{project_id}/turnaround/generate", response_model=GenerationResult, status_code=201)
def generate_turnaround(project_id: str, data: Generate, request: Request, db: Session = Depends(get_db), registry=Depends(get_registry)):
    project = get_project_or_404(db, project_id)
    turn, jobs = create_turn(db, registry, project)
    finish(db, request, jobs, data.confirmed)
    return {"id": turn.id, "job_ids": [j.id for j in jobs]}


@router.post("/api/projects/{project_id}/turnaround/{version_id}/views/{angle}/regenerate", response_model=GenerationResult, status_code=201)
def regenerate_view(project_id: str, version_id: str, angle: str, request: Request, db: Session = Depends(get_db), registry=Depends(get_registry)):
    project = get_project_or_404(db, project_id)
    previous = owned(db, TurnaroundVersion, project_id, version_id)
    if angle not in ANGLES:
        fail("invalid_angle", "Góc không hợp lệ", 400)
    if previous.master_version_id != project.approved_master_id:
        fail("stale_turnaround", "Hãy tạo turnaround từ nhân vật gốc đã duyệt hiện tại")
    turn, jobs = create_turn(db, registry, project, previous, angle)
    finish(db, request, jobs, True)
    return {"id": turn.id, "job_ids": [j.id for j in jobs]}


@router.post("/api/projects/{project_id}/turnaround/{version_id}/approve")
def approve_turnaround(project_id: str, version_id: str, db: Session = Depends(get_db)):
    project = get_project_or_404(db, project_id)
    turn = owned(db, TurnaroundVersion, project_id, version_id)
    if turn.master_version_id != project.approved_master_id:
        fail("stale_turnaround", "Turnaround dựa trên nhân vật gốc cũ")
    views = [v for v in turn.views if v.selected]
    if {v.angle for v in views} != set(ANGLES) or any(v.job.status != JobStatus.SUCCEEDED or not v.job.output_asset_ids for v in views):
        fail("turnaround_not_ready", "Cần đủ sáu góc tạo thành công trước khi duyệt")
    if project.approved_turnaround_id != turn.id:
        db.add(ApprovalEvent(project_id=project_id, target_type="turnaround", target_id=turn.id, previous_id=project.approved_turnaround_id))
        project.approved_turnaround_id = turn.id
        turn.approved_at = datetime.now(timezone.utc)
        db.commit()
    return {"approved_turnaround_id": turn.id}
