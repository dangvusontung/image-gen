from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.config import SPEND_LIMIT_USD_PER_DAY
from app.database import get_db
from app.jobs.service import spent_last_24h
from app.providers.base import CapabilityError, ImageProvider, ModelInfo, ProviderError
from app.providers.registry import ProviderRegistry, get_registry
from app.schemas import ConnectionTestResult, ModelOut, ProviderOut

router = APIRouter(prefix="/api", tags=["providers"])


def _model_out(m: ModelInfo) -> ModelOut:
    return ModelOut(
        id=m.id,
        display_name=m.display_name,
        max_reference_images=m.max_reference_images,
        aspect_ratios=list(m.aspect_ratios),
        default_aspect_ratio=m.default_aspect_ratio,
        price_per_image_usd=m.price_per_image_usd,
        price_note=m.price_note,
        status=m.status,
        notes=m.notes,
        default=m.default,
    )


def _provider_out(p: ImageProvider) -> ProviderOut:
    return ProviderOut(
        name=p.name,
        display_name=p.display_name,
        selectable=p.selectable,
        key_configured=p.key_configured,
        enabled=p.selectable and p.key_configured,
        info_url=p.info_url,
        data_notice=p.data_notice,
        models=[_model_out(m) for m in p.models()],
    )


def _provider(registry: ProviderRegistry, name: str) -> ImageProvider:
    try:
        return registry.get(name)
    except CapabilityError as exc:
        raise HTTPException(404, detail={"code": exc.code, "message": exc.message})


@router.get("/providers", response_model=list[ProviderOut])
def list_providers(registry: ProviderRegistry = Depends(get_registry)):
    return [_provider_out(p) for p in registry.all()]


@router.get("/providers/{provider}/models", response_model=list[ModelOut])
def list_models(provider: str, registry: ProviderRegistry = Depends(get_registry)):
    return [_model_out(m) for m in _provider(registry, provider).models()]


@router.post("/providers/{provider}/test", response_model=ConnectionTestResult)
async def test_provider(provider: str, registry: ProviderRegistry = Depends(get_registry)):
    p = _provider(registry, provider)
    try:
        return ConnectionTestResult(ok=True, message=await p.test_connection())
    except ProviderError as exc:
        return ConnectionTestResult(ok=False, message=exc.message, code=exc.code)


class SpendOut(BaseModel):
    spent_24h_usd: float
    limit_usd: float


@router.get("/spend", response_model=SpendOut)
def spend(db: Session = Depends(get_db)):
    return SpendOut(spent_24h_usd=round(spent_last_24h(db), 4), limit_usd=SPEND_LIMIT_USD_PER_DAY)
