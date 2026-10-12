from datetime import datetime
from typing import Any, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

WorkflowMode = Literal["manual", "hybrid", "hybrid_gemini"]

AssetKind = Literal["reference", "side_profile", "template"]


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
    selected: bool = True
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
    workflow_mode: WorkflowMode = "manual"
    preset_id: Optional[str] = None


class ProjectSummary(BaseModel):
    id: str
    name: str
    description: Optional[str]
    rights_confirmed: bool
    provider: str
    model: str
    workflow_mode: WorkflowMode = "manual"
    created_at: datetime
    updated_at: datetime
    asset_count: int
    thumbnail_asset_id: Optional[str]
    completed_jobs: int = 0
    active_jobs: int = 0
    failed_jobs: int = 0
    recent_activity: Optional[str] = None


class ProjectDetail(BaseModel):
    id: str
    name: str
    description: Optional[str]
    rights_confirmed: bool
    provider: str
    model: str
    workflow_mode: WorkflowMode = "manual"
    step_leads: dict[str, str] = {}
    step_templates: dict[str, str] = {}
    preset_id: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    assets: list[AssetResponse]


WorkflowStep = Literal["master", "turnaround", "concept", "enhance"]


class StepLeadUpdate(BaseModel):
    step: WorkflowStep
    #: None clears the override and returns the step to its automatic choice.
    lead: Optional[str] = None


class StepTemplateUpdate(BaseModel):
    step: WorkflowStep
    #: None clears the template, so the step uses prompt text alone for art direction.
    asset_id: Optional[str] = None


class AssetOrderUpdate(BaseModel):
    asset_ids: list[str]


class AssetUpdate(BaseModel):
    kind: Optional[AssetKind] = None
    selected: Optional[bool] = None


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
    sizes: list[str] = []
    default_size: Optional[str] = None
    price_table: dict[str, float] = {}


class PresetStep(BaseModel):
    provider: str
    model: str
    size: Optional[str] = None


class PresetIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    #: Only the steps you want to pin; anything missing falls back to the project's own settings.
    steps: dict[WorkflowStep, PresetStep] = {}


class PresetOut(BaseModel):
    id: str
    name: str
    steps: dict[str, PresetStep]
    created_at: datetime
    updated_at: datetime


class ProviderOut(BaseModel):
    name: str
    display_name: str
    selectable: bool
    key_configured: bool
    enabled: bool
    info_url: Optional[str]
    data_notice: Optional[str]
    models: list[ModelOut]
    #: Set when the provider can list the account's own models; names where the list came from.
    catalogue_source: Optional[str] = None
    catalogue_fetched_at: Optional[datetime] = None
    supports_text: bool = False


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


class JobHistoryOut(JobOut):
    """A job plus the project it belongs to, for the cross-project history view."""

    project_name: str


class HealthResponse(BaseModel):
    status: str
    message: str


class ConceptProposalOut(BaseModel):
    id: str
    run: int
    slot: int
    title: str
    brief: dict[str, str]
    master_version_id: str
    created_at: datetime


class ConceptOut(BaseModel):
    id: str
    run: int
    slot: int
    revision: int
    mood: str
    camera: str
    brief: dict[str, str]
    master_version_id: str
    turnaround_version_id: Optional[str]
    stale: bool
    job: JobOut
    created_at: datetime


class EnhancementOut(BaseModel):
    id: str
    concept_id: str
    number: int
    master_version_id: str
    turnaround_version_id: Optional[str]
    stale: bool
    job: JobOut
    created_at: datetime


class GenerationResult(BaseModel):
    id: Optional[str] = None
    job_ids: list[str]
    concept_ids: list[str] = []


class ReferencePlan(BaseModel):
    provider: str
    model: str
    size: str | None = None
    reference_asset_ids: list[str]
    reference_labels: list[str]
    omitted_asset_ids: list[str]
    warning: Optional[str]
    estimated_cost_usd: Optional[float]
    master_version_id: str
    turnaround_version_id: Optional[str]


class MasterOut(BaseModel):
    id: str
    round: int
    variant: int
    job: JobOut


class TurnaroundViewOut(BaseModel):
    angle: str
    job: JobOut


class TurnaroundOut(BaseModel):
    id: str
    number: int
    master_version_id: str
    stale: bool
    approved_at: Optional[datetime]
    views: list[TurnaroundViewOut]


class ApprovalOut(BaseModel):
    target_type: str
    target_id: str
    previous_id: Optional[str]
    created_at: datetime


class WorkflowOut(BaseModel):
    approved_master_id: Optional[str]
    approved_turnaround_id: Optional[str]
    masters: list[MasterOut]
    turnarounds: list[TurnaroundOut]
    approvals: list[ApprovalOut]


class PromptOut(BaseModel):
    name: str
    body: str
    source: str
    template_version: int
    revision: Optional[int]
