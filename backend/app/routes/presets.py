"""Reusable per-step provider/model presets, shared by every project."""

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Preset, Project
from app.providers.base import CapabilityError
from app.providers.registry import ProviderRegistry, get_registry
from app.schemas import PresetIn, PresetOut

router = APIRouter(prefix="/api/presets", tags=["presets"])


def _out(preset: Preset) -> PresetOut:
    return PresetOut(id=preset.id, name=preset.name, steps=preset.steps or {},
                     created_at=preset.created_at, updated_at=preset.updated_at)


def _validated(registry: ProviderRegistry, data: PresetIn) -> dict:
    """Refuse a preset that names a provider or model this install cannot use."""
    steps: dict[str, dict] = {}
    for step, choice in data.steps.items():
        try:
            provider = registry.get(choice.provider)
            if not provider.selectable:
                raise CapabilityError("provider_disabled", f"{provider.display_name} không tạo ảnh được")
            model = provider.get_model(choice.model)
            if choice.size and choice.size not in model.sizes:
                raise CapabilityError(
                    "unsupported_size",
                    f"{model.display_name} không hỗ trợ kích thước {choice.size} "
                    f"(hỗ trợ: {', '.join(model.sizes) or 'mặc định'})")
        except CapabilityError as exc:
            raise HTTPException(400, detail={"code": exc.code, "message": f"Bước {step}: {exc.message}"})
        steps[step] = {"provider": choice.provider, "model": choice.model, "size": choice.size}
    return steps


def _preset_or_404(db: Session, preset_id: str) -> Preset:
    preset = db.get(Preset, preset_id)
    if preset is None:
        raise HTTPException(404, detail={"code": "preset_not_found", "message": "Không tìm thấy bộ cấu hình"})
    return preset


@router.get("", response_model=list[PresetOut])
def list_presets(db: Session = Depends(get_db)):
    return [_out(p) for p in db.query(Preset).order_by(Preset.name).all()]


@router.post("", response_model=PresetOut, status_code=201)
def create_preset(data: PresetIn, db: Session = Depends(get_db), registry=Depends(get_registry)):
    preset = Preset(name=data.name.strip(), steps=_validated(registry, data))
    db.add(preset)
    db.commit()
    db.refresh(preset)
    return _out(preset)


@router.put("/{preset_id}", response_model=PresetOut)
def update_preset(preset_id: str, data: PresetIn, db: Session = Depends(get_db), registry=Depends(get_registry)):
    preset = _preset_or_404(db, preset_id)
    preset.name, preset.steps = data.name.strip(), _validated(registry, data)
    preset.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(preset)
    return _out(preset)


@router.delete("/{preset_id}", status_code=204)
def delete_preset(preset_id: str, db: Session = Depends(get_db)):
    preset = _preset_or_404(db, preset_id)
    # Projects using it fall back to their own provider/model rather than breaking.
    for project in db.query(Project).filter(Project.preset_id == preset.id):
        project.preset_id = None
    db.delete(preset)
    db.commit()
