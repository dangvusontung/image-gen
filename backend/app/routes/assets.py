from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.builtin import builtin_reference, is_builtin
from app.config import UPLOAD_MAX_SIZE
from app.database import get_db
from app.models import SOURCE_KINDS, Asset, Project
from app.schemas import AssetKind, AssetOrderUpdate, AssetResponse, AssetUpdate
from app.storage.local import LocalStorage
from app.storage.validation import InvalidImage, sanitize_filename, validate_image

router = APIRouter(tags=["assets"])
storage = LocalStorage()

MAX_REFERENCE_PHOTOS = 8
MAX_SIDE_PROFILE_PHOTOS = 4
MAX_TEMPLATE_PHOTOS = 8
_LIMITS = {"reference": MAX_REFERENCE_PHOTOS, "side_profile": MAX_SIDE_PROFILE_PHOTOS,
           "template": MAX_TEMPLATE_PHOTOS}


def _error(status: int, code: str, message: str) -> HTTPException:
    return HTTPException(status_code=status, detail={"code": code, "message": message})


def _project(db: Session, project_id: str) -> Project:
    project = db.get(Project, project_id)
    if not project:
        raise _error(404, "project_not_found", "Không tìm thấy dự án")
    return project


def _asset(db: Session, asset_id: str) -> Asset:
    asset = db.get(Asset, asset_id)
    if not asset:
        raise _error(404, "asset_not_found", "Không tìm thấy ảnh")
    return asset


def _source_asset(db: Session, asset_id: str) -> Asset:
    asset = _asset(db, asset_id)
    if asset.kind not in SOURCE_KINDS:
        raise _error(409, "asset_not_editable", "Ảnh do hệ thống tạo không sửa/xoá ở đây")
    return asset


@router.get("/api/projects/{project_id}/assets", response_model=list[AssetResponse])
def list_assets(project_id: str, db: Session = Depends(get_db)):
    return _project(db, project_id).source_assets


@router.post("/api/projects/{project_id}/assets", response_model=list[AssetResponse], status_code=201)
async def upload_assets(
    project_id: str,
    files: list[UploadFile] = File(...),
    kind: AssetKind = Form("reference"),
    db: Session = Depends(get_db),
):
    project = _project(db, project_id)
    if not project.rights_confirmed:
        raise _error(403, "rights_not_confirmed", "Cần xác nhận quyền sử dụng ảnh trước khi tải lên")

    existing = sum(1 for a in project.source_assets if a.kind == kind)
    if existing + len(files) > _LIMITS[kind]:
        raise _error(400, "too_many_photos", f"Tối đa {_LIMITS[kind]} ảnh loại này (hiện có {existing})")

    # Validate everything before writing anything so a bad file doesn't leave a partial upload.
    validated = []
    for upload in files:
        data = await upload.read(UPLOAD_MAX_SIZE + 1)
        name = sanitize_filename(upload.filename)
        try:
            validated.append((name, data, validate_image(data, UPLOAD_MAX_SIZE)))
        except InvalidImage as exc:
            raise _error(400, "invalid_image", f"{name}: {exc}")

    position = max((a.position for a in project.source_assets), default=-1) + 1
    saved_paths = []
    try:
        created = []
        for name, data, info in validated:
            rel_path = storage.save(data, project_id, info.ext)
            saved_paths.append(rel_path)
            asset = Asset(
                project_id=project_id,
                kind=kind,
                filename=name,
                file_path=rel_path,
                size=len(data),
                content_type=info.content_type,
                width=info.width,
                height=info.height,
                position=position,
            )
            position += 1
            db.add(asset)
            created.append(asset)
        db.commit()
    except Exception:
        db.rollback()
        for p in saved_paths:
            storage.delete(p)
        raise
    for asset in created:
        db.refresh(asset)
    return created


@router.put("/api/projects/{project_id}/assets/order", response_model=list[AssetResponse])
def reorder_assets(project_id: str, data: AssetOrderUpdate, db: Session = Depends(get_db)):
    project = _project(db, project_id)
    by_id = {a.id: a for a in project.source_assets}
    if sorted(data.asset_ids) != sorted(by_id):
        raise _error(400, "invalid_order", "Danh sách ảnh không khớp với dự án")
    for index, asset_id in enumerate(data.asset_ids):
        by_id[asset_id].position = index
    db.commit()
    db.refresh(project)
    return project.source_assets


@router.patch("/api/assets/{asset_id}", response_model=AssetResponse)
def update_asset(asset_id: str, data: AssetUpdate, db: Session = Depends(get_db)):
    asset = _source_asset(db, asset_id)
    changed = False
    if data.kind is not None and data.kind != asset.kind:
        count = sum(1 for a in asset.project.source_assets if a.kind == data.kind)
        if count >= _LIMITS[data.kind]:
            raise _error(400, "too_many_photos", f"Tối đa {_LIMITS[data.kind]} ảnh loại này")
        asset.kind = data.kind
        changed = True
    if data.selected is not None and data.selected != asset.selected:
        asset.selected = data.selected
        changed = True
    if changed:
        db.commit()
        db.refresh(asset)
    return asset


@router.get("/api/assets/{asset_id}/content")
def download_asset(asset_id: str, db: Session = Depends(get_db)):
    # References shipped with the app are files, not rows, but still have to display.
    if is_builtin(asset_id):
        entry = builtin_reference(asset_id)
        if entry is None:
            raise _error(404, "asset_not_found", "Không tìm thấy ảnh")
        path, label = entry
        return FileResponse(
            path,
            media_type=f"image/{path.suffix.lstrip('.').replace('jpg', 'jpeg')}",
            filename=path.name,
            content_disposition_type="inline",
            headers={"X-Content-Type-Options": "nosniff", "Cache-Control": "private, max-age=3600"},
        )
    asset = _asset(db, asset_id)
    try:
        path = storage.path_for(asset.file_path)
    except (FileNotFoundError, ValueError):
        raise _error(404, "asset_file_missing", "File ảnh không còn trên đĩa")
    return FileResponse(
        path,
        media_type=asset.content_type,
        filename=asset.filename,
        content_disposition_type="inline",
        headers={"X-Content-Type-Options": "nosniff", "Cache-Control": "private, max-age=3600"},
    )


@router.delete("/api/assets/{asset_id}", status_code=204)
def delete_asset(asset_id: str, db: Session = Depends(get_db)):
    asset = _source_asset(db, asset_id)
    rel_path = asset.file_path
    db.delete(asset)
    db.commit()
    storage.delete(rel_path)
