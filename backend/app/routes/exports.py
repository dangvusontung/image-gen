import io
import json
import tempfile
import zipfile
from typing import Literal

from fastapi import APIRouter, Depends, Query
from fastapi.encoders import jsonable_encoder
from fastapi.responses import FileResponse, Response, StreamingResponse
from PIL import Image, ImageDraw, ImageOps
from sqlalchemy.orm import Session
from starlette.background import BackgroundTask

from app.database import get_db
from app.models import Asset, Concept, GenerationJob, JobStatus
from app.routes.assets import _asset, storage
from app.routes.projects import get_project_or_404
from app.routes.workflow import fail
from app.schemas import JobOut

router = APIRouter(tags=["downloads & exports"])


def file_for(asset):
    try:
        return storage.path_for(asset.file_path)
    except (FileNotFoundError, ValueError):
        fail("asset_file_missing", "File ảnh không còn trên đĩa", 404)


def converted(asset, fmt):
    with Image.open(file_for(asset)) as image:
        image = ImageOps.exif_transpose(image)
        if fmt == "jpeg":
            if "A" in image.getbands():
                bg = Image.new("RGB", image.size, "white")
                bg.paste(image, mask=image.getchannel("A"))
                image = bg
            else:
                image = image.convert("RGB")
        else:
            image = image.convert("RGBA" if "A" in image.getbands() else "RGB")
        data = io.BytesIO()
        image.save(data, format="JPEG" if fmt == "jpeg" else "PNG", **({"quality": 95} if fmt == "jpeg" else {}))
        return data.getvalue()


@router.get("/api/assets/{asset_id}/download")
def download(asset_id: str, format: Literal["original", "png", "jpeg"] = "original", db: Session = Depends(get_db)):
    asset = _asset(db, asset_id)
    if format == "original":
        return FileResponse(file_for(asset), media_type=asset.content_type, filename=asset.filename,
                            headers={"X-Content-Type-Options": "nosniff"})
    return Response(converted(asset, format), media_type=f"image/{format}",
                    headers={"Content-Disposition": f'attachment; filename="{asset.id}.{format}"', "X-Content-Type-Options": "nosniff"})


def contact_sheet(db, project_id, run=None):
    concepts = db.query(Concept).filter_by(project_id=project_id).order_by(Concept.run.desc(), Concept.revision.desc()).all()
    target_run = run or max((c.run for c in concepts), default=0)
    selected = {}
    for c in concepts:
        if c.run == target_run and c.slot not in selected:
            selected[c.slot] = c
    if not selected:
        fail("no_concepts", "Chưa có concept để xuất bảng ảnh", 400)
    slots = list(range(1, 10))
    width, height, pad, caption, cols = 384, 512, 16, 40, 3
    rows = (len(slots) + cols - 1) // cols
    sheet = Image.new("RGB", (cols * (width + pad) + pad, rows * (height + caption + pad) + pad), "#f1f0ed")
    draw = ImageDraw.Draw(sheet)
    for index, slot in enumerate(slots):
        x = pad + (index % cols) * (width + pad)
        y = pad + (index // cols) * (height + caption + pad)
        concept = selected.get(slot)
        if concept and concept.job.status == JobStatus.SUCCEEDED and concept.job.output_asset_ids:
            asset = db.get(Asset, concept.job.output_asset_ids[0])
            if asset is not None:
                with Image.open(file_for(asset)) as image:
                    image = ImageOps.contain(ImageOps.exif_transpose(image).convert("RGB"), (width, height))
                    sheet.paste(image, (x + (width - image.width) // 2, y + (height - image.height) // 2))
        else:
            draw.rectangle((x, y, x + width, y + height), fill="#dedbd5")
            draw.text((x + 16, y + 30), concept.job.status if concept else "empty", fill="#404040")
        label = f"{slot}. {concept.mood}" if concept else f"Slot {slot}"
        draw.text((x, y + height + 12), label, fill="#202020")
    data = io.BytesIO()
    sheet.save(data, format="PNG")
    return data.getvalue()


@router.get("/api/projects/{project_id}/contact-sheet")
def download_sheet(project_id: str, run: int | None = Query(default=None, ge=1), db: Session = Depends(get_db)):
    get_project_or_404(db, project_id)
    return Response(contact_sheet(db, project_id, run), media_type="image/png",
                    headers={"Content-Disposition": 'attachment; filename="concepts.png"'})


@router.get("/api/projects/{project_id}/export")
def export_project(project_id: str, db: Session = Depends(get_db)):
    project = get_project_or_404(db, project_id)
    assets = db.query(Asset).filter_by(project_id=project_id).order_by(Asset.created_at).all()
    jobs = db.query(GenerationJob).filter_by(project_id=project_id).order_by(GenerationJob.created_at).all()
    archive = tempfile.SpooledTemporaryFile(max_size=8 * 1024 * 1024)
    try:
        with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED) as zipped:
            entries = []
            for asset in assets:
                path = file_for(asset)
                name = f"images/{asset.kind}/{asset.id}{path.suffix}"
                zipped.write(path, name)
                entries.append({"id": asset.id, "filename": asset.filename, "kind": asset.kind, "job_id": asset.job_id, "archive_path": name})
            manifest = {"project_id": project.id, "workflow_mode": project.workflow_mode, "name": project.name, "approved_master_id": project.approved_master_id,
                        "approved_turnaround_id": project.approved_turnaround_id, "assets": entries,
                        "jobs": [JobOut.model_validate(j).model_dump() for j in jobs]}
            zipped.writestr("manifest.json", json.dumps(jsonable_encoder(manifest), ensure_ascii=False, indent=2))
            if db.query(Concept).filter_by(project_id=project_id).first():
                zipped.writestr("contact-sheet.png", contact_sheet(db, project_id))
        archive.seek(0)
    except BaseException:
        archive.close()
        raise

    def chunks():
        while chunk := archive.read(64 * 1024):
            yield chunk

    return StreamingResponse(chunks(), media_type="application/zip", background=BackgroundTask(archive.close),
                             headers={"Content-Disposition": f'attachment; filename="project-{project_id}.zip"'})


@router.get("/api/projects/{project_id}/concepts/download")
def download_concepts(project_id: str, db: Session = Depends(get_db)):
    get_project_or_404(db, project_id)
    concepts = db.query(Concept).filter_by(project_id=project_id).order_by(Concept.run, Concept.slot, Concept.revision).all()
    archive = tempfile.SpooledTemporaryFile(max_size=8 * 1024 * 1024)
    count = 0
    try:
        with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_STORED) as zipped:
            for concept in concepts:
                if concept.job.status != JobStatus.SUCCEEDED:
                    continue
                for index, asset_id in enumerate(concept.job.output_asset_ids, start=1):
                    asset = db.get(Asset, asset_id)
                    if asset is None or asset.project_id != project_id:
                        continue
                    path = file_for(asset)
                    zipped.write(path, f"run-{concept.run}/concept-{concept.slot:02d}-v{concept.revision}-{index}{path.suffix}")
                    count += 1
        if not count:
            fail("no_concepts", "Chưa có ảnh concept hoàn tất để tải", 400)
        archive.seek(0)
    except BaseException:
        archive.close()
        raise

    def chunks():
        while chunk := archive.read(64 * 1024):
            yield chunk

    return StreamingResponse(chunks(), media_type="application/zip", background=BackgroundTask(archive.close),
                             headers={"Content-Disposition": f'attachment; filename="concepts-{project_id}.zip"'})
