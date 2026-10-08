import json
from typing import Literal

from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.concept_planning import SLOTS, fresh_brief
from app.concept_options import ConceptChoices, MENU, apply_choices, style_instruction
from app.database import get_db
from app.generation_policy import generation_target
from app.jobs.service import estimate_job_cost
from app.models import Asset, Concept, EnhancementVersion, JobStatus, MasterVersion, TurnaroundVersion
from app.providers.base import CapabilityError
from app.providers.registry import get_registry
from app.routes.projects import get_project_or_404
from app.routes.workflow import fail, finish, output, owned, queue, snapshot
from app.schemas import ConceptOut, EnhancementOut, GenerationResult, JobOut, ReferencePlan

router = APIRouter(prefix="/api/projects/{project_id}", tags=["concepts & enhancements"])


class BatchRequest(BaseModel):
    choices: ConceptChoices | None = None
    count: int | None = Field(default=None, ge=1, le=5)
    batch: Literal["A", "B"]
    confirmed: bool = False
    size: str | None = None


class ImageSettings(BaseModel):
    size: str | None = None


class RegenerateRequest(ImageSettings):
    choices: ConceptChoices | None = None


@router.get("/concept-options")
def concept_options(project_id: str, db: Session = Depends(get_db)):
    get_project_or_404(db, project_id)
    return MENU


class EnhanceRequest(ImageSettings):
    confirm_reference_subset: bool = False


class EstimateOut(BaseModel):
    per_image_usd: float | None
    total_usd: float | None
    reference_count: int
    note: str


@router.get("/generation-estimate", response_model=EstimateOut)
def generation_estimate(project_id: str, purpose: Literal["master", "turnaround", "concept"],
                        count: int = Query(default=1, ge=1, le=9), size: str | None = None,
                        db: Session = Depends(get_db), registry=Depends(get_registry)):
    project = get_project_or_404(db, project_id)
    if purpose == "master":
        refs = [a.id for a in db.query(Asset).filter(Asset.project_id == project_id, Asset.kind.in_(["reference", "side_profile"]))]
    else:
        _, master_asset, turn = identity(db, project)
        refs = [master_asset]
        if purpose == "concept":
            refs += [a for a, _ in turn_refs(turn)]
        else:
            refs += [a.id for a in db.query(Asset).filter_by(project_id=project_id, kind="side_profile")]
    try:
        provider_name, model_id, default_size = generation_target(project, purpose)
        size = size or default_size
        provider = registry.get(provider_name)
        model = provider.get_model(model_id)
        if size and size not in model.sizes:
            fail("unsupported_size", "Kích thước không được model hỗ trợ", 400)
        price = estimate_job_cost(db, provider, model, refs, size)
    except CapabilityError as exc:
        fail(exc.code, exc.message, 400)
    return EstimateOut(per_image_usd=price, total_usd=price * count if price is not None else None,
                       reference_count=len(refs), note="Ước tính theo model và kích thước; Gemini chưa gồm token đầu vào/văn bản. Chi phí thực có thể khác.")


def identity(db, project):
    if not project.approved_master_id:
        fail("master_required", "Tạo và duyệt nhân vật gốc trước")
    master = owned(db, MasterVersion, project.id, project.approved_master_id)
    master_asset = output(db, master)
    turn = owned(db, TurnaroundVersion, project.id, project.approved_turnaround_id) if project.approved_turnaround_id else None
    if turn and turn.master_version_id != master.id:
        fail("stale_turnaround", "Turnaround không khớp nhân vật gốc hiện tại")
    return master, master_asset, turn


def turn_refs(turn, camera=""):
    if not turn:
        return []
    preferred = "front"
    for fragment, angle in (("left three", "left45"), ("right three", "right45"), ("right profile", "right90"),
                            ("left profile", "left90"), ("over-the-shoulder", "back")):
        if fragment in camera:
            preferred = angle
    views = sorted((v for v in turn.views if v.selected), key=lambda v: (v.angle != preferred, v.angle))
    return [(v.job.output_asset_ids[0], f"TURNAROUND {v.angle}, angle guidance only")
            for v in views if v.job.status == JobStatus.SUCCEEDED and v.job.output_asset_ids]


def concept_out(concept, project):
    return ConceptOut(
        id=concept.id, batch=concept.batch, run=concept.run, slot=concept.slot, revision=concept.revision,
        mood=concept.mood, camera=concept.camera, brief=concept.brief, master_version_id=concept.master_version_id,
        turnaround_version_id=concept.turnaround_version_id, stale=concept.master_version_id != project.approved_master_id,
        job=JobOut.model_validate(concept.job), created_at=concept.created_at,
    )


@router.get("/concepts", response_model=list[ConceptOut])
def list_concepts(project_id: str, db: Session = Depends(get_db)):
    project = get_project_or_404(db, project_id)
    rows = db.query(Concept).filter_by(project_id=project_id).order_by(Concept.run.desc(), Concept.slot, Concept.revision.desc()).all()
    return [concept_out(c, project) for c in rows]


def new_concept(db, registry, project, batch, run, slot, mood, camera, revision, size, choices=None):
    master, master_asset, turn = identity(db, project)
    prior = db.query(Concept).filter_by(project_id=project.id).order_by(Concept.created_at).all()
    brief = fresh_brief([c.brief for c in prior], slot, camera)
    if choices is not None:
        brief = apply_choices(brief, choices, slot, [c.brief for c in prior])
    prompt, meta = snapshot(db, project.id, "concept", mood=mood, camera=camera,
                            prior_briefs=json.dumps([c.brief for c in prior[-18:]], ensure_ascii=False),
                            brief=json.dumps(brief, ensure_ascii=False))
    if choices is not None:
        prompt += "\nUser styling choices take priority over default scene/outfit suggestions. Follow the selected outfit, scene, activity and lighting in the concept brief exactly. Keep the master identity; reference clothing and backgrounds are not outfit or scene instructions."
        prompt += "\n" + style_instruction(choices)
        meta["concept_choices"] = choices.model_dump()
    refs = [(master_asset, "MASTER identity authority")] + turn_refs(turn, camera)
    meta.update(master_version_id=master.id, turnaround_version_id=turn.id if turn else None,
                batch=batch, slot=slot, run=run, revision=revision, mood=mood, camera=camera, brief=brief,
                reference_labels=[label for _, label in refs])
    job = queue(db, registry, project, purpose="concept", prompt=prompt,
                reference_asset_ids=[asset for asset, _ in refs], aspect_ratio="3:4", size=size, meta=meta)
    db.flush()
    concept = Concept(project_id=project.id, batch=batch, run=run, slot=slot, revision=revision, mood=mood,
                      camera=camera, brief=brief, master_version_id=master.id,
                      turnaround_version_id=turn.id if turn else None, job_id=job.id)
    db.add(concept)
    db.flush()
    return concept, job


@router.post("/concepts/generate", response_model=GenerationResult, status_code=201)
def generate_batch(project_id: str, data: BatchRequest, request: Request, db: Session = Depends(get_db), registry=Depends(get_registry)):
    project = get_project_or_404(db, project_id)
    run = (db.query(func.max(Concept.run)).filter_by(project_id=project_id, batch=data.batch).scalar() or 0) + 1
    jobs, concepts = [], []
    # Rotate all nine camera assignments on later runs, preserving complete coverage across A+B.
    cameras = [s[2] for s in SLOTS]
    selected_slots = SLOTS[:5] if data.batch == "A" else SLOTS[5:]
    if data.count is not None and data.count > len(selected_slots):
        fail("invalid_count", "Batch B tối đa 4 ảnh", 400)
    for slot, mood, default_camera in selected_slots[:data.count]:
        camera = cameras[(slot - 1 + run - 1) % len(cameras)]
        concept, job = new_concept(db, registry, project, data.batch, run, slot, mood, camera, 1, data.size, data.choices)
        concepts.append(concept)
        jobs.append(job)
    finish(db, request, jobs, data.confirmed)
    return GenerationResult(job_ids=[j.id for j in jobs], concept_ids=[c.id for c in concepts])


@router.post("/concepts/{concept_id}/regenerate", response_model=GenerationResult, status_code=201)
def regenerate(project_id: str, concept_id: str, data: RegenerateRequest, request: Request, db: Session = Depends(get_db), registry=Depends(get_registry)):
    project = get_project_or_404(db, project_id)
    old = owned(db, Concept, project_id, concept_id)
    revision = (db.query(func.max(Concept.revision)).filter_by(project_id=project_id, batch=old.batch, run=old.run, slot=old.slot).scalar() or 0) + 1
    concept, job = new_concept(db, registry, project, old.batch, old.run, old.slot, old.mood, old.camera, revision, data.size, data.choices or (ConceptChoices.model_validate(old.job.meta["concept_choices"]) if old.job.meta.get("concept_choices") else None))
    finish(db, request, [job], True)
    return GenerationResult(id=concept.id, job_ids=[job.id], concept_ids=[concept.id])


def enhancement_plan(db, registry, project, concept, size):
    purpose = "enhance"
    if concept.job.status != JobStatus.SUCCEEDED or not concept.job.output_asset_ids:
        fail("concept_not_ready", "Concept phải tạo thành công trước khi nâng cấp")
    master, master_asset, turn = identity(db, project)
    try:
        provider_name, model_id, default_size = generation_target(project, purpose)
        size = size or default_size
        provider = registry.get(provider_name)
        model = provider.get_model(model_id)
    except CapabilityError as exc:
        fail(exc.code, exc.message, 400)
    refs = [(master_asset, "MASTER identity authority"), (concept.job.output_asset_ids[0], "SELECTED CONCEPT scene and composition authority")]
    angles = turn_refs(turn, concept.camera)
    refs += angles[:1] if project.workflow_mode != "manual" else angles
    if model.max_reference_images < 2:
        fail("reference_limit_exceeded", "Nâng cấp cần ít nhất hai ảnh: master và concept", 400)
    kept, dropped = refs[:model.max_reference_images], refs[model.max_reference_images:]
    warning = None
    if dropped:
        warning = (f"Model nhận tối đa {model.max_reference_images} ảnh; sẽ bỏ {len(dropped)} góc turnaround. "
                   "Ưu tiên master, concept đã chọn, rồi góc phù hợp. Xác nhận để tiếp tục.")
    return ReferencePlan(reference_asset_ids=[a for a, _ in kept], reference_labels=[label for _, label in kept],
                         omitted_asset_ids=[a for a, _ in dropped], warning=warning,
                         provider=provider_name, model=model_id, size=size or model.default_size,
                         estimated_cost_usd=estimate_job_cost(db, provider, model, [a for a, _ in kept], size), master_version_id=master.id,
                         turnaround_version_id=turn.id if turn else None)


@router.get("/concepts/{concept_id}/enhance-plan", response_model=ReferencePlan)
def get_enhancement_plan(project_id: str, concept_id: str, size: str | None = None, db: Session = Depends(get_db), registry=Depends(get_registry)):
    project = get_project_or_404(db, project_id)
    return enhancement_plan(db, registry, project, owned(db, Concept, project_id, concept_id), size)


@router.post("/concepts/{concept_id}/enhance", response_model=GenerationResult, status_code=201)
def enhance(project_id: str, concept_id: str, data: EnhanceRequest, request: Request, db: Session = Depends(get_db), registry=Depends(get_registry)):
    project = get_project_or_404(db, project_id)
    concept = owned(db, Concept, project_id, concept_id)
    plan = enhancement_plan(db, registry, project, concept, data.size)
    if plan.warning and not data.confirm_reference_subset:
        fail("reference_subset_confirmation_required", plan.warning, 400)
    prompt, meta = snapshot(db, project_id, "enhance")
    # Record the exact source scene even if the user later approves a different master.
    prompt += "\nPreserve this selected scene brief: " + json.dumps(concept.brief, ensure_ascii=False)
    meta.update(plan.model_dump(), concept_id=concept.id, source_concept_master_id=concept.master_version_id)
    job = queue(db, registry, project, purpose="enhance", prompt=prompt,
                reference_asset_ids=plan.reference_asset_ids, aspect_ratio="3:4", size=data.size, meta=meta)
    db.flush()
    number = (db.query(func.max(EnhancementVersion.number)).filter_by(concept_id=concept_id).scalar() or 0) + 1
    version = EnhancementVersion(project_id=project_id, concept_id=concept_id, number=number,
                                 master_version_id=plan.master_version_id, turnaround_version_id=plan.turnaround_version_id, job_id=job.id)
    db.add(version)
    finish(db, request, [job], True)
    return GenerationResult(id=version.id, job_ids=[job.id])


@router.get("/enhancements", response_model=list[EnhancementOut])
def list_enhancements(project_id: str, db: Session = Depends(get_db)):
    project = get_project_or_404(db, project_id)
    return [EnhancementOut(id=e.id, concept_id=e.concept_id, number=e.number, master_version_id=e.master_version_id,
                           turnaround_version_id=e.turnaround_version_id, stale=e.master_version_id != project.approved_master_id,
                           job=JobOut.model_validate(e.job), created_at=e.created_at)
            for e in db.query(EnhancementVersion).filter_by(project_id=project_id).order_by(EnhancementVersion.created_at.desc()).all()]
