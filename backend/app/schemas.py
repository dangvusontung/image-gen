from datetime import datetime
from typing import Any, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

AssetKind = Literal["reference", "side_profile"]


class AssetResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    kind: str
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


class ProjectSummary(BaseModel):
    id: str
    name: str
    description: Optional[str]
    rights_confirmed: bool
    created_at: datetime
    updated_at: datetime
    asset_count: int
    thumbnail_asset_id: Optional[str]


class ProjectDetail(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    description: Optional[str]
    rights_confirmed: bool
    created_at: datetime
    updated_at: datetime
    assets: list[AssetResponse]


class AssetOrderUpdate(BaseModel):
    asset_ids: list[str]


class AssetUpdate(BaseModel):
    kind: AssetKind


class ProviderInfo(BaseModel):
    name: str
    enabled: bool
    capabilities: dict[str, Any]


class HealthResponse(BaseModel):
    status: str
    message: str
