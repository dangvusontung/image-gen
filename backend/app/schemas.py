from datetime import datetime
from typing import Any, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

AssetKind = Literal["reference", "side_profile"]


class AssetResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    kind: str
    job_id: Optional[str] = None
    filename: str
    size: int
    content_type: str
    width: Optional[int]
    height: Optional[int]
    position: int
    created_at: datetime


class ProjectCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    description: Optional[str] = None


class ProjectUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=255)
    description: Optional[str] = None
    rights_confirmed: Optional[bool] = None
    provider: Optional[str] = None
    model: Optional[str] = None


class ProjectSummary(BaseModel):
    id: str
    name: str
    description: Optional[str]
    rights_confirmed: bool
    provider: str
    model: str
    created_at: datetime
    updated_at: datetime
    asset_count: int
    thumbnail_asset_id: Optional[str]


class ProjectDetail(BaseModel):
    id: str
    name: str
    description: Optional[str]
    rights_confirmed: bool
    provider: str
    model: str
    created_at: datetime
    updated_at: datetime
    assets: list[AssetResponse]


class AssetOrderUpdate(BaseModel):
    asset_ids: list[str]


class AssetUpdate(BaseModel):
    kind: AssetKind


class ModelOut(BaseModel):
    id: str
    display_name: str
    max_reference_images: int
    aspect_ratios: list[str]
    default_aspect_ratio: str
    price_per_image_usd: Optional[float]
    price_note: Optional[str]
    status: str
    notes: Optional[str]
    default: bool


class ProviderOut(BaseModel):
    name: str
    display_name: str
    selectable: bool
    key_configured: bool
    enabled: bool
    info_url: Optional[str]
    data_notice: Optional[str]
    models: list[ModelOut]


class ConnectionTestResult(BaseModel):
    ok: bool
    message: str
    code: Optional[str] = None


class JobOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    project_id: str
    purpose: str
    provider: str
    model: str
    prompt: str
    settings: dict[str, Any]
    reference_asset_ids: list[str]
    meta: dict[str, Any]
    status: str
    attempts: int
    max_attempts: int
    next_attempt_at: Optional[datetime]
    cancel_requested: bool
    provider_request_id: Optional[str]
    error_code: Optional[str]
    error_message: Optional[str]
    output_asset_ids: list[str]
    estimated_cost_usd: Optional[float]
    actual_cost_usd: Optional[float]
    created_at: datetime
    updated_at: datetime
    started_at: Optional[datetime]
    submitted_at: Optional[datetime]
    finished_at: Optional[datetime]


class HealthResponse(BaseModel):
    status: str
    message: str
