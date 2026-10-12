import json
import random
import re
from typing import Literal

from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.concept_defaults import DEFAULT_CONCEPTS
from app.concept_options import ConceptChoices, MENU, apply_choices, style_instruction
from app.database import get_db
from app.generation_policy import generation_target
from app.jobs.service import estimate_job_cost
from app.models import Asset, Concept, ConceptProposal, EnhancementVersion, JobStatus, MasterVersion, TurnaroundVersion
from app.providers.base import CapabilityError, ProviderError, ReferenceImage
from app.providers.registry import get_registry
from app.routes.projects import get_project_or_404
from app.routes.workflow import TEMPLATE_NOTE, fail, finish, output, owned, queue, snapshot, step_template
from app.routes.assets import storage
from app.storage.images import prepare_reference
from app.schemas import ConceptOut, ConceptProposalOut, EnhancementOut, GenerationResult, JobOut, ReferencePlan

router = APIRouter(prefix="/api/projects/{project_id}", tags=["concepts & enhancements"])


class GenerateRequest(BaseModel):
    """Render the picked concepts; empty means all nine."""
    proposal_ids: list[str] = Field(default_factory=list, max_length=9)
    #: Slot numbers, used when rendering the built-in concepts rather than proposed ones.
    slots: list[int] = Field(default_factory=list, max_length=9)
    #: Per-slot edits to the concept wording, merged over whatever that slot would otherwise use.
    briefs: dict[int, dict[str, str]] = Field(default_factory=dict)
    #: Per-slot title overrides.
    titles: dict[int, str] = Field(default_factory=dict)
    #: Build images from the styling menu alone, independent of the nine concepts.
    custom: bool = False
    count: int = Field(default=1, ge=1, le=4)
    choices: ConceptChoices | None = None
    confirmed: bool = False
    size: str | None = None


class ImageSettings(BaseModel):
    size: str | None = None


class RegenerateRequest(ImageSettings):
    choices: ConceptChoices | None = None
    #: Edited brief fields, merged over the concept's own. Used to get past a moderation block.
    brief: dict[str, str] | None = None
    #: Replaces the concept's title.
    title: str | None = Field(default=None, max_length=255)


@router.get("/concept-options")
def concept_options(project_id: str, db: Session = Depends(get_db)):
    get_project_or_404(db, project_id)
    return MENU


class EnhanceRequest(ImageSettings):
    confirm_reference_subset: bool = False
    #: Polish this earlier enhancement instead of the concept, to keep iterating on a result.
    from_enhancement_id: str | None = None
    #: Replaces the enhance template for this run; blank falls back to the template.
    prompt: str | None = Field(default=None, max_length=8000)


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
        refs = [a.id for a in db.query(Asset).filter(Asset.project_id == project_id, Asset.kind.in_(["reference", "side_profile"]),
                                                     Asset.selected.is_(True))]
        template = step_template(db, project, "master")
        if template:
            refs.append(template[0])
    else:
        _, master_asset, turn = identity(db, project)
        refs = [master_asset]
        if purpose == "concept":
            refs += [a for a, _ in concept_turn_ref(turn, "", (project.step_leads or {}).get("concept"))]
            template = step_template(db, project, "concept")
            if template:
                refs.append(template[0])
        else:
            refs += [a.id for a in db.query(Asset).filter(Asset.project_id == project_id, Asset.kind.in_(["reference", "side_profile"]), Asset.selected.is_(True))]
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


def preferred_angle(camera="", lead=None):
    """The angle a concept's camera wording implies, or None when nothing matches."""
    if lead:
        return lead
    if "frontal" in camera or "straight-on" in camera:
        return "front"
    for fragment, angle in (("left three", "left45"), ("right three", "right45"), ("right profile", "right90"),
                            ("left profile", "left90"), ("over-the-shoulder", "back")):
        if fragment in camera:
            return angle
    return None


def concept_turn_ref(turn, camera="", lead=None):
    """One angle per concept: the pinned one, else the camera's, else a random available angle.

    Sending all six crowds the request and pushes most concepts toward the front view.
    """
    if lead == "none":
        return []
    available = turn_refs(turn)
    if not available:
        return []
    wanted = preferred_angle(camera, lead)
    if wanted:
        match = [ref for ref in turn_refs(turn, camera, lead) if f"TURNAROUND {wanted}," in ref[1]]
        if match:
            return match[:1]
        if wanted == "front":
            return []
    return [random.SystemRandom().choice(available)]


def turn_refs(turn, camera="", lead=None):
    if not turn:
        return []
    preferred = "front"
    for fragment, angle in (("left three", "left45"), ("right three", "right45"), ("right profile", "right90"),
                            ("left profile", "left90"), ("over-the-shoulder", "back")):
        if fragment in camera:
            preferred = angle
    views = [v for v in turn.views if v.selected]
    # A pinned angle wins over the camera wording, but only if that view exists.
    if lead and any(v.angle == lead for v in views):
        preferred = lead
    views = sorted(views, key=lambda v: (v.angle != preferred, v.angle))
    return [(v.job.output_asset_ids[0], f"TURNAROUND {v.angle}, angle guidance only")
            for v in views if v.job.status == JobStatus.SUCCEEDED and v.job.output_asset_ids]


def concept_out(concept, project):
    return ConceptOut(
        id=concept.id, run=concept.run, slot=concept.slot, revision=concept.revision,
        mood=concept.mood, camera=concept.camera, brief=concept.brief, master_version_id=concept.master_version_id,
        turnaround_version_id=concept.turnaround_version_id, stale=concept.master_version_id != project.approved_master_id,
        job=JobOut.model_validate(concept.job), created_at=concept.created_at,
    )


@router.get("/concepts", response_model=list[ConceptOut])
def list_concepts(project_id: str, db: Session = Depends(get_db)):
    project = get_project_or_404(db, project_id)
    rows = db.query(Concept).filter_by(project_id=project_id).order_by(Concept.run.desc(), Concept.slot, Concept.revision.desc()).all()
    return [concept_out(c, project) for c in rows if not c.job.dismissed]


def new_concept(db, registry, project, run, slot, mood, camera, revision, size, choices=None, brief=None):
    master, master_asset, turn = identity(db, project)
    prior = db.query(Concept).filter_by(project_id=project.id).order_by(Concept.created_at).all()
    # An all-auto menu must leave each concept exactly as written.
    if choices is not None and choices.overrides_concept():
        brief = apply_choices(brief, choices, slot, [c.brief for c in prior])
    else:
        choices = None
    prompt, meta = snapshot(db, project.id, "concept", mood=mood, camera=camera,
                            prior_briefs=json.dumps([c.brief for c in prior[-18:]], ensure_ascii=False),
                            brief=json.dumps(brief, ensure_ascii=False))
    if choices is not None:
        prompt += "\nUser styling choices take priority over default scene/outfit suggestions. Follow the selected outfit, scene, activity and lighting in the concept brief exactly. Keep the master identity; reference clothing and backgrounds are not outfit or scene instructions."
        styling = style_instruction(choices)
        if styling:
            prompt += "\n" + styling
        meta["concept_choices"] = choices.model_dump()
    refs = [(master_asset, "MASTER identity authority")] + concept_turn_ref(turn, camera, (project.step_leads or {}).get("concept"))
    template = step_template(db, project, "concept")
    if template:
        prompt += TEMPLATE_NOTE
        refs.append(template)
    meta.update(master_version_id=master.id, turnaround_version_id=turn.id if turn else None,
                slot=slot, run=run, revision=revision, mood=mood, camera=camera, brief=brief,
                reference_labels=[label for _, label in refs])
    job = queue(db, registry, project, purpose="concept", prompt=prompt,
                reference_asset_ids=[asset for asset, _ in refs], aspect_ratio="3:4", size=size, meta=meta)
    db.flush()
    concept = Concept(project_id=project.id, run=run, slot=slot, revision=revision, mood=mood,
                      camera=camera, brief=brief, master_version_id=master.id,
                      turnaround_version_id=turn.id if turn else None, job_id=job.id)
    db.add(concept)
    db.flush()
    return concept, job


#: Custom images are numbered from here, clear of the nine concept slots.
CUSTOM_SLOT_BASE = 101
#: A deliberately plain starting point: the styling menu supplies everything that matters.
NEUTRAL_BRIEF = {
    "setting": "a simple setting suited to the outfit",
    "activity": "a relaxed natural moment",
    "pose": "a comfortable natural stance",
    "outfit": "a simple contemporary outfit",
    "silhouette": "simple contemporary clothes",
    "expression": "a natural relaxed expression",
    "gaze": "toward the camera",
    "camera": "eye-level three-quarter",
    "framing": "three-quarter-body",
    "lighting": "soft natural light",
}

PROPOSAL_FIELDS = ("setting", "activity", "pose", "outfit", "silhouette", "expression", "gaze", "camera", "framing", "lighting")


def parse_proposals(text: str) -> list[dict]:
    """The model is asked for a bare JSON array; tolerate fences and surrounding chatter."""
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```[a-zA-Z]*\n?|\n?```$", "", cleaned).strip()
    if not cleaned.startswith("["):
        opened, closed = cleaned.find("["), cleaned.rfind("]")
        if opened == -1 or closed <= opened:
            fail("proposals_unparsable", "Không đọc được danh sách concept do model trả về", 502)
        cleaned = cleaned[opened:closed + 1]
    try:
        items = json.loads(cleaned)
    except ValueError:
        fail("proposals_unparsable", "Không đọc được danh sách concept do model trả về", 502)
    if not isinstance(items, list) or not items:
        fail("proposals_unparsable", "Model không trả về concept nào", 502)
    parsed = []
    for index, item in enumerate(items[:9], start=1):
        if not isinstance(item, dict):
            fail("proposals_unparsable", "Concept do model trả về không đúng định dạng", 502)
        brief = {key: str(item.get(key) or "").strip() for key in PROPOSAL_FIELDS}
        if not brief["setting"] or not brief["activity"]:
            fail("proposals_incomplete", f"Concept {index} thiếu bối cảnh hoặc hoạt động", 502)
        parsed.append({"title": str(item.get("title") or f"Concept {index}").strip()[:255], "brief": brief})
    if len(parsed) < 9:
        fail("proposals_incomplete", f"Model chỉ đề xuất {len(parsed)}/9 concept", 502)
    return parsed


def proposal_out(row):
    return ConceptProposalOut(id=row.id, run=row.run, slot=row.slot, title=row.title, brief=row.brief,
                              master_version_id=row.master_version_id, created_at=row.created_at)


@router.get("/concept-proposals", response_model=list[ConceptProposalOut])
def list_proposals(project_id: str, db: Session = Depends(get_db)):
    """The model-proposed round if there is one, else the built-in nine the prompt renders."""
    project = get_project_or_404(db, project_id)
    latest = db.query(func.max(ConceptProposal.run)).filter_by(project_id=project.id).scalar()
    if latest is None:
        return [
            ConceptProposalOut(id=f"default-{index}", run=0, slot=index, title=concept["title"],
                               brief={k: v for k, v in concept.items() if k != "title"},
                               master_version_id=project.approved_master_id or "",
                               created_at=project.created_at)
            for index, concept in enumerate(DEFAULT_CONCEPTS, start=1)
        ]
    rows = db.query(ConceptProposal).filter_by(project_id=project.id, run=latest).order_by(ConceptProposal.slot).all()
    return [proposal_out(r) for r in rows]


@router.post("/concept-proposals", response_model=list[ConceptProposalOut], status_code=201)
async def propose_concepts(project_id: str, db: Session = Depends(get_db), registry=Depends(get_registry)):
    """Ask a text-capable model to invent nine concepts for the approved master. No images yet."""
    project = get_project_or_404(db, project_id)
    master, master_asset, _turn = identity(db, project)
    provider = registry.get(project.provider)
    if not provider.supports_text:
        # Fall back to any configured provider that can answer with text, so an image-only
        # project is not blocked from proposing concepts.
        provider = next((p for p in registry.all() if p.supports_text and p.selectable and p.key_configured), None)
        if provider is None:
            fail("text_unsupported",
                 "Chưa có nhà cung cấp nào hỗ trợ văn bản để đề xuất concept. "
                 "Cấu hình API key cho một nhà cung cấp có model văn bản (ví dụ Gemini) rồi thử lại.", 400)
    prompt, _meta = snapshot(db, project_id, "concept_proposal")
    asset = db.get(Asset, master_asset)
    try:
        raw = storage.path_for(asset.file_path).read_bytes()
        data, mime = prepare_reference(raw)
    except (FileNotFoundError, ValueError, OSError):
        fail("reference_missing", "Không đọc được ảnh nhân vật gốc trên đĩa", 409)
    reference = ReferenceImage(data, mime, "MASTER CHARACTER")
    try:
        answer = await provider.generate_text(prompt, [reference])
    except ProviderError as exc:
        fail(exc.code, exc.message, 502)
    run = (db.query(func.max(ConceptProposal.run)).filter_by(project_id=project_id).scalar() or 0) + 1
    rows = [
        ConceptProposal(project_id=project_id, master_version_id=master.id, run=run, slot=index,
                        title=item["title"], brief=item["brief"])
        for index, item in enumerate(parse_proposals(answer), start=1)
    ]
    db.add_all(rows)
    db.commit()
    for row in rows:
        db.refresh(row)
    return [proposal_out(r) for r in rows]


@router.post("/concepts/generate", response_model=GenerationResult, status_code=201)
def generate_concepts(project_id: str, data: GenerateRequest, request: Request, db: Session = Depends(get_db), registry=Depends(get_registry)):
    """Render the chosen proposals. Each proposal keeps its slot, so reruns stay comparable."""
    project = get_project_or_404(db, project_id)
    if data.custom:
        if data.choices is None or not data.choices.overrides_concept():
            fail("choices_required", "Chọn ít nhất một mục trong menu trang phục/bối cảnh", 400)
        run = (db.query(func.max(Concept.run)).filter_by(project_id=project_id).scalar() or 0) + 1
        # Custom images sit above the nine so they never collide with a concept slot.
        base_slot = CUSTOM_SLOT_BASE
        jobs, concepts = [], []
        for index in range(data.count):
            concept, job = new_concept(db, registry, project, run, base_slot + index, "Tùy chỉnh",
                                       NEUTRAL_BRIEF["camera"], 1, data.size, data.choices,
                                       brief=dict(NEUTRAL_BRIEF))
            concepts.append(concept)
            jobs.append(job)
        finish(db, request, jobs, data.confirmed)
        return GenerationResult(job_ids=[j.id for j in jobs], concept_ids=[c.id for c in concepts])
    latest = db.query(func.max(ConceptProposal.run)).filter_by(project_id=project_id).scalar()
    if latest is None:
        # No model-proposed round: render the built-in nine straight from the prompt.
        chosen = [(index, dict(c)) for index, c in enumerate(DEFAULT_CONCEPTS, start=1)]
        if data.slots:
            chosen = [(slot, brief) for slot, brief in chosen if slot in data.slots]
            if not chosen:
                fail("invalid_slots", "Không có concept nào khớp lựa chọn", 400)
    else:
        query = db.query(ConceptProposal).filter_by(project_id=project_id, run=latest)
        if data.proposal_ids:
            query = query.filter(ConceptProposal.id.in_(data.proposal_ids))
        proposals = query.order_by(ConceptProposal.slot).all()
        if data.proposal_ids and len(proposals) != len(set(data.proposal_ids)):
            fail("proposal_not_found", "Có concept không thuộc đợt đề xuất mới nhất", 404)
        chosen = [(p.slot, {"title": p.title, **p.brief}) for p in proposals]
    run = (db.query(func.max(Concept.run)).filter_by(project_id=project_id).scalar() or 0) + 1
    jobs, concepts = [], []
    unknown = sorted({k for edit in data.briefs.values() for k in edit} - set(PROPOSAL_FIELDS))
    if unknown:
        fail("unknown_brief_field", f"Trường không hợp lệ: {', '.join(unknown)}", 400)
    for slot, brief in chosen:
        title = (data.titles.get(slot) or brief.pop("title", f"Concept {slot}")).strip()
        brief.pop("title", None)
        brief.update({k: v.strip() for k, v in data.briefs.get(slot, {}).items()})
        concept, job = new_concept(db, registry, project, run, slot, title,
                                   brief.get("camera", ""), 1, data.size, data.choices, brief=brief)
        concepts.append(concept)
        jobs.append(job)
    finish(db, request, jobs, data.confirmed)
    return GenerationResult(job_ids=[j.id for j in jobs], concept_ids=[c.id for c in concepts])


@router.post("/concepts/{concept_id}/regenerate", response_model=GenerationResult, status_code=201)
def regenerate(project_id: str, concept_id: str, data: RegenerateRequest, request: Request, db: Session = Depends(get_db), registry=Depends(get_registry)):
    project = get_project_or_404(db, project_id)
    old = owned(db, Concept, project_id, concept_id)
    revision = (db.query(func.max(Concept.revision)).filter_by(project_id=project_id, run=old.run, slot=old.slot).scalar() or 0) + 1
    brief = dict(old.brief)
    if data.brief:
        unknown = sorted(set(data.brief) - set(PROPOSAL_FIELDS))
        if unknown:
            fail("unknown_brief_field", f"Trường không hợp lệ: {', '.join(unknown)}", 400)
        brief.update({k: v.strip() for k, v in data.brief.items()})
    camera = brief.get("camera") or old.camera
    concept, job = new_concept(db, registry, project, old.run, old.slot, (data.title or old.mood).strip(), camera,
                               revision, data.size,
                               data.choices or (ConceptChoices.model_validate(old.job.meta["concept_choices"]) if old.job.meta.get("concept_choices") else None),
                               brief=brief)
    finish(db, request, [job], True)
    return GenerationResult(id=concept.id, job_ids=[job.id], concept_ids=[concept.id])


def enhance_source(db, concept, from_enhancement_id):
    """The image to polish: the concept itself, or a previous enhancement of it to iterate on."""
    if not from_enhancement_id:
        if concept.job.status != JobStatus.SUCCEEDED or not concept.job.output_asset_ids:
            fail("concept_not_ready", "Concept phải tạo thành công trước khi nâng cấp")
        return concept.job.output_asset_ids[0], "SELECTED CONCEPT scene and composition authority"
    version = db.get(EnhancementVersion, from_enhancement_id)
    if version is None or version.concept_id != concept.id:
        fail("enhancement_not_found", "Không tìm thấy bản nâng cấp này của concept", 404)
    if version.job.status != JobStatus.SUCCEEDED or not version.job.output_asset_ids:
        fail("enhancement_not_ready", "Bản nâng cấp nguồn chưa tạo thành công")
    return version.job.output_asset_ids[0], f"PREVIOUS ENHANCEMENT {version.number}, scene and composition authority"


def enhancement_plan(db, registry, project, concept, size, from_enhancement_id=None):
    purpose = "enhance"
    source_asset, source_label = enhance_source(db, concept, from_enhancement_id)
    master, master_asset, turn = identity(db, project)
    try:
        provider_name, model_id, default_size = generation_target(project, purpose)
        size = size or default_size
        provider = registry.get(provider_name)
        model = provider.get_model(model_id)
    except CapabilityError as exc:
        fail(exc.code, exc.message, 400)
    # Enhancing is an edit of one picture: send only the image being edited, so the provider
    # has nothing else to blend in.
    refs = [(source_asset, source_label)]
    if model.max_reference_images < 1:
        fail("reference_limit_exceeded", "Model không nhận ảnh tham chiếu nào", 400)
    kept, dropped = refs[:model.max_reference_images], refs[model.max_reference_images:]
    warning = None
    if dropped:
        warning = (f"Model nhận tối đa {model.max_reference_images} ảnh; sẽ bỏ {len(dropped)} ảnh tham chiếu phụ. "
                   "Ưu tiên master, concept đã chọn, rồi góc phù hợp. Xác nhận để tiếp tục.")
    return ReferencePlan(reference_asset_ids=[a for a, _ in kept], reference_labels=[label for _, label in kept],
                         omitted_asset_ids=[a for a, _ in dropped], warning=warning,
                         provider=provider_name, model=model_id, size=size or model.default_size,
                         estimated_cost_usd=estimate_job_cost(db, provider, model, [a for a, _ in kept], size), master_version_id=master.id,
                         turnaround_version_id=turn.id if turn else None)


@router.get("/concepts/{concept_id}/enhance-plan", response_model=ReferencePlan)
def get_enhancement_plan(project_id: str, concept_id: str, size: str | None = None,
                        from_enhancement_id: str | None = None,
                        db: Session = Depends(get_db), registry=Depends(get_registry)):
    project = get_project_or_404(db, project_id)
    return enhancement_plan(db, registry, project, owned(db, Concept, project_id, concept_id), size, from_enhancement_id)


@router.post("/concepts/{concept_id}/enhance", response_model=GenerationResult, status_code=201)
def enhance(project_id: str, concept_id: str, data: EnhanceRequest, request: Request, db: Session = Depends(get_db), registry=Depends(get_registry)):
    project = get_project_or_404(db, project_id)
    concept = owned(db, Concept, project_id, concept_id)
    plan = enhancement_plan(db, registry, project, concept, data.size, data.from_enhancement_id)
    if plan.warning and not data.confirm_reference_subset:
        fail("reference_subset_confirmation_required", plan.warning, 400)
    prompt, meta = snapshot(db, project_id, "enhance")
    if data.prompt and data.prompt.strip():
        # What the user typed stands in for the template; the job still records both.
        prompt = data.prompt.strip()
        meta["custom_prompt"] = True
    # The source image already is the scene, so the brief would only repeat it back as text.
    meta.update(concept_brief=concept.brief)
    meta.update(plan.model_dump(), concept_id=concept.id, source_concept_master_id=concept.master_version_id,
                from_enhancement_id=data.from_enhancement_id)
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
            for e in db.query(EnhancementVersion).filter_by(project_id=project_id).order_by(EnhancementVersion.created_at.desc()).all() if not e.job.dismissed]
