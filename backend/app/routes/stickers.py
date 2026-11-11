import io
import json
import zipfile
from typing import Literal

from fastapi import APIRouter, Depends, Request
from fastapi.responses import Response
from pydantic import BaseModel, Field, field_validator, model_validator
from PIL import Image
from sqlalchemy.orm import Session

from app.database import get_db
from app.jobs.service import estimate_job_cost
from app.models import Asset, GenerationJob, JobStatus, Project, StickerPack
from app.providers.base import CapabilityError
from app.providers.registry import get_registry
from app.routes.assets import storage
from app.routes.projects import _detail, get_project_or_404
from app.routes.workflow import fail, finish, output, owned, queue
from app.models import MasterVersion
from app.schemas import JobOut
from app.stickers import ARTWORK_VERSION, DEFAULT_ITEMS, artwork_matches, compose_sticker, concept_prompt, encode_webp, sticker_image, sticker_prompt

router = APIRouter(prefix="/api/sticker-packs", tags=["sticker packs"])


class StickerItem(BaseModel):
    id: str = Field(pattern=r"^[a-zA-Z0-9_-]{1,40}$")
    expression: str = Field(min_length=1, max_length=500)
    caption: str = Field(default="", max_length=120)
    emoji: str = Field(default="🙂", min_length=1, max_length=16)
    text_style: Literal["caption", "speech", "thought"] = "caption"
    text_x: float = Field(default=.5, ge=0, le=1)
    text_y: float = Field(default=.84, ge=0, le=1)
    text_size: int = Field(default=48, ge=24, le=64)
    text_color: str = Field(default="#302a3b", pattern=r"^#[0-9a-fA-F]{6}$")

    @field_validator("expression")
    @classmethod
    def nonblank(cls, value):
        if not value.strip():
            raise ValueError("Expression cannot be blank")
        return value.strip()


class PackSettings(BaseModel):
    name: str = Field(default="My sticker pack", min_length=1, max_length=128)
    publisher: str = Field(default="Made with Sticker Studio", min_length=1, max_length=128)
    style: Literal["chibi", "clay", "comic", "kawaii"] = "chibi"
    concept_brief: str = Field(default="", max_length=2000)
    items: list[StickerItem] = Field(default_factory=lambda: [StickerItem(**i) for i in DEFAULT_ITEMS], min_length=1, max_length=30)

    @field_validator("name", "publisher")
    @classmethod
    def nonblank(cls, value):
        if not value.strip():
            raise ValueError("Cannot be blank")
        return value.strip()

    @model_validator(mode="after")
    def unique_items(self):
        if len({i.id for i in self.items}) != len(self.items):
            raise ValueError("Sticker IDs must be unique")
        return self


class CreatePack(PackSettings):
    rights_confirmed: bool = False
    source_project_id: str | None = None


class GeneratePack(BaseModel):
    item_ids: list[str] = Field(min_length=1, max_length=30)
    confirmed: bool = False
    size: str | None = None


def get_pack(db, pack_id):
    pack = db.get(StickerPack, pack_id)
    if pack is None:
        fail("pack_not_found", "Sticker pack not found", 404)
    return pack


def pack_jobs(db, pack):
    return db.query(GenerationJob).filter_by(project_id=pack.project_id, purpose="sticker").order_by(GenerationJob.created_at.desc()).all()


def concept_jobs(db, pack):
    return db.query(GenerationJob).filter_by(project_id=pack.project_id, purpose="sticker_concept").order_by(GenerationJob.created_at.desc()).all()


def selected_photos(pack):
    return [a.id for a in pack.project.source_assets if a.selected and a.kind in ("reference", "side_profile")]


def current_concept(pack, job):
    return (job.project_id == pack.project_id and job.purpose == "sticker_concept"
            and job.status == JobStatus.SUCCEEDED and bool(job.output_asset_ids)
            and job.meta.get("style") == pack.style
            and job.meta.get("concept_brief", "") == pack.concept_brief
            and job.reference_asset_ids == selected_photos(pack))


def approved_concept(db, pack, required=False):
    job = db.get(GenerationJob, pack.approved_concept_id) if pack.approved_concept_id else None
    asset = db.get(Asset, job.output_asset_ids[0]) if job and job.output_asset_ids else None
    if job is None or not current_concept(pack, job) or asset is None or asset.project_id != pack.project_id:
        if required:
            fail("concept_required", "Generate and approve a character concept first")
        return None
    return job


def pack_detail(db, pack):
    latest = {}
    for job in pack_jobs(db, pack):
        latest.setdefault(job.meta.get("sticker_id"), JobOut.model_validate(job))
    approved = approved_concept(db, pack)
    return {
        "id": pack.project_id, "name": pack.project.name, "publisher": pack.publisher,
        "style": pack.style, "concept_brief": pack.concept_brief, "items": pack.items,
        "project": _detail(pack.project), "jobs": latest,
        "approved_concept": JobOut.model_validate(approved) if approved else None,
        "concepts": [{"job": JobOut.model_validate(j), "current": current_concept(pack, j)} for j in concept_jobs(db, pack)],
    }


@router.get("")
def list_packs(db: Session = Depends(get_db)):
    packs = db.query(StickerPack).join(Project).order_by(Project.updated_at.desc()).all()
    return [{"id": p.project_id, "name": p.project.name, "style": p.style,
             "count": len(p.items), "reference_id": p.project.source_assets[0].id if p.project.source_assets else None}
            for p in packs]


@router.post("", status_code=201)
def create_pack(data: CreatePack, db: Session = Depends(get_db)):
    source_asset = None
    if data.source_project_id:
        if not data.rights_confirmed:
            fail("rights_not_confirmed", "Confirm rights to use this character first", 403)
        source = get_project_or_404(db, data.source_project_id)
        if not source.rights_confirmed:
            fail("rights_not_confirmed", "The source project has not confirmed photo rights", 403)
        if not source.approved_master_id:
            fail("master_required", "Approve a character in Character Studio first")
        master = owned(db, MasterVersion, source.id, source.approved_master_id)
        source_asset = db.get(Asset, output(db, master))
    project = Project(name=data.name, rights_confirmed=data.rights_confirmed)
    db.add(project)
    db.flush()
    pack = StickerPack(project=project, publisher=data.publisher, style=data.style,
                       concept_brief=data.concept_brief, items=[i.model_dump() for i in data.items])
    db.add(pack)
    saved_path = None
    try:
        if source_asset:
            saved_path = storage.save(storage.path_for(source_asset.file_path).read_bytes(), project.id,
                                      source_asset.file_path.rsplit(".", 1)[-1])
            db.add(Asset(project_id=project.id, kind="reference", filename="character-reference.png",
                         file_path=saved_path, content_type=source_asset.content_type, size=source_asset.size,
                         width=source_asset.width, height=source_asset.height, position=0))
        db.commit()
    except Exception:
        db.rollback()
        if saved_path:
            storage.delete(saved_path)
        raise
    db.refresh(project)
    return pack_detail(db, pack)


@router.get("/{pack_id}")
def read_pack(pack_id: str, db: Session = Depends(get_db)):
    return pack_detail(db, get_pack(db, pack_id))


@router.put("/{pack_id}")
def update_pack(pack_id: str, data: PackSettings, db: Session = Depends(get_db)):
    pack = get_pack(db, pack_id)
    if any(j.status in JobStatus.ACTIVE for j in [*pack_jobs(db, pack), *concept_jobs(db, pack)]):
        fail("pack_busy", "Wait for generation to finish before editing the pack")
    if data.style != pack.style or data.concept_brief != pack.concept_brief:
        pack.approved_concept_id = None
    pack.project.name, pack.publisher, pack.style = data.name, data.publisher, data.style
    pack.concept_brief = data.concept_brief
    pack.items = [i.model_dump() for i in data.items]
    db.commit()
    return pack_detail(db, pack)


def reference_ids(pack):
    refs = selected_photos(pack)
    if not refs:
        fail("reference_required", "Upload a character or photo first", 400)
    return refs


@router.get("/{pack_id}/estimate")
def estimate_pack(pack_id: str, count: int = 1, size: str | None = None, purpose: Literal["sticker", "concept"] = "sticker",
                  db: Session = Depends(get_db), registry=Depends(get_registry)):
    pack = get_pack(db, pack_id)
    if not 1 <= count <= 30:
        fail("invalid_count", "Choose between 1 and 30 stickers", 400)
    refs = reference_ids(pack) if purpose == "concept" else [approved_concept(db, pack, required=True).output_asset_ids[0]]
    try:
        provider = registry.get(pack.project.provider)
        model = provider.get_model(pack.project.model)
        size = size or model.default_size
        provider.check_request(model.id, len(refs), "1:1", size)
        price = estimate_job_cost(db, provider, model, refs, size)
    except CapabilityError as exc:
        fail(exc.code, exc.message, 400)
    return {"per_image_usd": price, "total_usd": price * count if price is not None else None,
            "count": count, "size": size, "provider": provider.name, "model": model.id}


class GenerateConcept(BaseModel):
    variants: int = Field(default=2, ge=1, le=4)
    confirmed: bool = False
    size: str | None = None


@router.post("/{pack_id}/concepts/generate")
def generate_concepts(pack_id: str, data: GenerateConcept, request: Request,
                      db: Session = Depends(get_db), registry=Depends(get_registry)):
    pack = get_pack(db, pack_id)
    if any(j.status in JobStatus.ACTIVE for j in [*concept_jobs(db, pack), *pack_jobs(db, pack)]):
        fail("pack_busy", "Wait for the current generation to finish")
    estimate = estimate_pack(pack_id, data.variants, data.size, "concept", db, registry)
    jobs = []
    for _ in range(data.variants):
        job = queue(db, registry, pack.project, purpose="sticker_concept", prompt=concept_prompt(pack.style, pack.concept_brief),
                    reference_asset_ids=reference_ids(pack), aspect_ratio="1:1", size=estimate["size"],
                    options={"sticker": True}, meta={"style": pack.style, "concept_brief": pack.concept_brief})
        db.flush()
        jobs.append(job)
    finish(db, request, jobs, data.confirmed)
    return [JobOut.model_validate(j) for j in jobs]


@router.post("/{pack_id}/concepts/{job_id}/approve")
def approve_concept(pack_id: str, job_id: str, db: Session = Depends(get_db)):
    pack = get_pack(db, pack_id)
    job = db.get(GenerationJob, job_id)
    if job is None or job.project_id != pack_id or job.purpose != "sticker_concept":
        fail("concept_not_found", "Character concept not found in this pack", 404)
    if any(j.status in JobStatus.ACTIVE for j in [*pack_jobs(db, pack), *concept_jobs(db, pack)]):
        fail("pack_busy", "Wait for generation to finish before changing the approved concept")
    if not current_concept(pack, job) or db.get(Asset, job.output_asset_ids[0]) is None:
        fail("concept_outdated", "Choose a finished concept made from the current photos, style and brief")
    pack.approved_concept_id = job.id
    db.commit()
    return pack_detail(db, pack)


@router.post("/{pack_id}/generate")
def generate_pack(pack_id: str, data: GeneratePack, request: Request,
                  db: Session = Depends(get_db), registry=Depends(get_registry)):
    pack = get_pack(db, pack_id)
    by_id = {item["id"]: item for item in pack.items}
    ids = list(dict.fromkeys(data.item_ids))
    if any(i not in by_id for i in ids):
        fail("sticker_not_found", "A selected sticker is not in this pack", 400)
    active = {j.meta.get("sticker_id") for j in pack_jobs(db, pack) if j.status in JobStatus.ACTIVE}
    if active.intersection(ids):
        fail("sticker_busy", "A selected sticker is already being generated")
    concept = approved_concept(db, pack, required=True)
    if any(j.status in JobStatus.ACTIVE for j in concept_jobs(db, pack)):
        fail("pack_busy", "Wait for concept generation to finish")
    estimate = estimate_pack(pack_id, len(ids), data.size, "sticker", db, registry)
    jobs = []
    for item_id in ids:
        job = queue(db, registry, pack.project, purpose="sticker", prompt=sticker_prompt(pack.style, by_id[item_id]),
                    reference_asset_ids=[concept.output_asset_ids[0]], aspect_ratio="1:1", size=estimate["size"],
                    options={"sticker": True}, meta={"sticker_id": item_id, "sticker_item": by_id[item_id], "style": pack.style, "artwork_version": ARTWORK_VERSION, "concept_job_id": concept.id, "reference_labels": ["APPROVED CHARACTER CONCEPT: identity, proportions, outfit and palette authority"]})
        db.flush()
        jobs.append(job)
    finish(db, request, jobs, data.confirmed)
    return [JobOut.model_validate(j) for j in jobs]


def ready_image(db, pack, item_id, job_id=None, draft=None):
    jobs = [j for j in pack_jobs(db, pack) if j.meta.get("sticker_id") == item_id]
    job = next((j for j in jobs if j.id == job_id), None) if job_id else next(iter(jobs), None)
    if job is None or job.status != JobStatus.SUCCEEDED or not job.output_asset_ids:
        fail("sticker_not_ready", "This sticker is not ready for export")
    item = next((i for i in pack.items if i["id"] == item_id), None)
    concept = approved_concept(db, pack, required=True)
    if item is None or not artwork_matches(job.meta, pack.style, item) or job.meta.get("concept_job_id") != concept.id:
        fail("sticker_outdated", "Regenerate this sticker to apply the saved changes")
    asset = db.get(Asset, job.output_asset_ids[0])
    if asset is None or asset.project_id != pack.project_id:
        fail("output_missing", "The generated image is missing", 404)
    try:
        return compose_sticker(sticker_image(storage.path_for(asset.file_path).read_bytes()), draft or item)
    except (OSError, ValueError) as exc:
        fail("sticker_processing_failed", str(exc), 422)


@router.get("/{pack_id}/stickers/{item_id}/image")
def preview_sticker(pack_id: str, item_id: str, job_id: str | None = None, db: Session = Depends(get_db)):
    pack = get_pack(db, pack_id)
    image = ready_image(db, pack, item_id, job_id)
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return Response(buffer.getvalue(), media_type="image/png", headers={"Cache-Control": "no-store"})


@router.post("/{pack_id}/stickers/{item_id}/preview")
def preview_dialogue(pack_id: str, item_id: str, data: StickerItem, db: Session = Depends(get_db)):
    pack = get_pack(db, pack_id)
    if data.id != item_id:
        fail("sticker_not_found", "Sticker ID does not match", 400)
    buffer = io.BytesIO()
    ready_image(db, pack, item_id, draft=data.model_dump()).save(buffer, format="PNG")
    return Response(buffer.getvalue(), media_type="image/png", headers={"Cache-Control": "no-store"})


class ExportPack(BaseModel):
    platform: Literal["whatsapp", "telegram"]
    item_ids: list[str] = Field(min_length=1, max_length=30)


@router.post("/{pack_id}/export")
def export_pack(pack_id: str, data: ExportPack, db: Session = Depends(get_db)):
    pack = get_pack(db, pack_id)
    ids = list(dict.fromkeys(data.item_ids))
    if data.platform == "whatsapp" and not 3 <= len(ids) <= 30:
        fail("pack_size_invalid", "WhatsApp packs need 3–30 stickers", 400)
    by_id = {i["id"]: i for i in pack.items}
    if any(i not in by_id for i in ids):
        fail("sticker_not_found", "A selected sticker is not in this pack", 400)
    buffer = io.BytesIO()
    stickers = []
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        for index, item_id in enumerate(ids):
            image = ready_image(db, pack, item_id)
            try:
                webp = encode_webp(image, 100 * 1024 if data.platform == "whatsapp" else 512 * 1024)
            except ValueError as exc:
                fail("sticker_too_large", str(exc), 422)
            filename = f"{index + 1:02d}-{item_id}.webp"
            archive.writestr(filename, webp)
            stickers.append({"image_file": filename, "emojis": [by_id[item_id]["emoji"]],
                             "accessibility_text": by_id[item_id]["expression"][:125]})
            if index == 0:
                tray = image.copy()
                tray.thumbnail((96, 96), Image.Resampling.LANCZOS)
                icon = io.BytesIO()
                tray.save(icon, format="PNG", optimize=True)
                archive.writestr("tray.png", icon.getvalue())
        metadata = {"identifier": pack.project_id, "name": pack.project.name, "publisher": pack.publisher,
                    "tray_image_file": "tray.png", "animated_sticker_pack": False, "stickers": stickers}
        archive.writestr("contents.json", json.dumps({"sticker_packs": [metadata]}, ensure_ascii=False, indent=2))
        if data.platform == "telegram":
            instructions = (
                "TELEGRAM\n1. Extract this ZIP. Open https://t.me/Stickers in Telegram.\n"
                "2. Send /newpack and your pack name.\n3. Send each numbered .webp as a FILE (not a photo), "
                "followed by its emoji from contents.json.\n4. Send /publish and follow the bot's instructions.\n"
                "tray.png and contents.json are metadata, not stickers to upload.\n"
            )
        else:
            instructions = (
                "WHATSAPP\n1. Extract this ZIP on your phone.\n2. In a sticker-maker app, create a pack "
                "with the name and publisher in contents.json.\n3. Import the numbered .webp files, "
                "choose tray.png as the pack icon, and use that app's Add to WhatsApp action.\n"
                "This ZIP is an asset bundle, not a file WhatsApp installs directly. "
                "Developers can also use contents.json with the official WhatsApp sticker sample app.\n"
            )
        archive.writestr("IMPORT.txt", instructions)
    return Response(buffer.getvalue(), media_type="application/zip",
                    headers={"Content-Disposition": f'attachment; filename="stickers-{data.platform}-{pack.project_id[:8]}.zip"'})
