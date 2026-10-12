import uuid
from datetime import datetime, timezone

from sqlalchemy import JSON, Boolean, Column, Float, ForeignKey, Index, Integer, String, Text, and_, true
from sqlalchemy.orm import foreign, relationship

from app.database import Base, UTCDateTime

SOURCE_KINDS = ("reference", "side_profile", "template")


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _uuid() -> str:
    return str(uuid.uuid4())


class Project(Base):
    __tablename__ = "projects"

    id = Column(String(36), primary_key=True, default=_uuid)
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    rights_confirmed = Column(Boolean, nullable=False, default=False)
    provider = Column(String(32), nullable=False, default="mock")
    model = Column(String(128), nullable=False, default="mock-v1")
    workflow_mode = Column(String(32), nullable=False, default="manual", server_default="manual")
    # Which reference leads each step: {"master": asset_id, "turnaround": asset_id,
    # "concept": angle, "enhance": angle}. Missing keys keep the automatic choice.
    step_leads = Column(JSON, nullable=False, default=dict, server_default="{}")
    # Which uploaded template image steers each step's art direction: {step: asset_id}.
    step_templates = Column(JSON, nullable=False, default=dict, server_default="{}")
    #: When set, the preset decides provider/model/size per step instead of workflow_mode.
    preset_id = Column(String(36), ForeignKey("presets.id", ondelete="SET NULL"), nullable=True)
    # Plain pointers (no FK) to avoid a projects<->versions FK cycle; maintained by the approval routes.
    approved_master_id = Column(String(36), nullable=True)
    approved_turnaround_id = Column(String(36), nullable=True)
    created_at = Column(UTCDateTime(), default=_now, nullable=False)
    updated_at = Column(UTCDateTime(), default=_now, onupdate=_now, nullable=False)

    assets = relationship("Asset", back_populates="project", cascade="all, delete-orphan", order_by="Asset.position")
    preset = relationship("Preset", lazy="joined")
    source_assets = relationship(
        "Asset",
        primaryjoin=lambda: and_(Project.id == foreign(Asset.project_id), Asset.kind.in_(SOURCE_KINDS)),
        order_by="Asset.position",
        viewonly=True,
    )
    jobs = relationship("GenerationJob", back_populates="project", cascade="all, delete-orphan")


class Asset(Base):
    __tablename__ = "assets"

    id = Column(String(36), primary_key=True, default=_uuid)
    project_id = Column(String(36), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    # "reference" | "side_profile" (user uploads) | "generated" (job output)
    kind = Column(String(32), nullable=False, default="reference")
    job_id = Column(String(36), ForeignKey("generation_jobs.id", ondelete="SET NULL"), nullable=True, index=True)
    filename = Column(String(255), nullable=False)
    file_path = Column(String(512), nullable=False)
    size = Column(Integer, nullable=False)
    content_type = Column(String(50), nullable=False)
    width = Column(Integer, nullable=True)
    height = Column(Integer, nullable=True)
    position = Column(Integer, nullable=False, default=0)
    # Deselected source photos stay in the project but are never sent to a provider.
    selected = Column(Boolean, nullable=False, default=True, server_default=true())
    created_at = Column(UTCDateTime(), default=_now, nullable=False)

    project = relationship("Project", back_populates="assets")


class JobStatus:
    QUEUED = "queued"
    SUBMITTING = "submitting"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"

    ACTIVE = (QUEUED, SUBMITTING, RUNNING)
    FINAL = (SUCCEEDED, FAILED, CANCELLED)


class GenerationJob(Base):
    __tablename__ = "generation_jobs"

    id = Column(String(36), primary_key=True, default=_uuid)
    project_id = Column(String(36), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    purpose = Column(String(32), nullable=False)  # "master" | "turnaround" | "concept" | "enhance" | "test"
    provider = Column(String(32), nullable=False)
    model = Column(String(128), nullable=False)
    prompt = Column(Text, nullable=False)
    settings = Column(JSON, nullable=False, default=dict)  # aspect_ratio, seed, provider options
    reference_asset_ids = Column(JSON, nullable=False, default=list)
    meta = Column(JSON, nullable=False, default=dict)  # links to domain entities (master version, slot…)

    status = Column(String(16), nullable=False, default=JobStatus.QUEUED)
    attempts = Column(Integer, nullable=False, default=0)
    max_attempts = Column(Integer, nullable=False, default=3)
    next_attempt_at = Column(UTCDateTime(), nullable=True)
    cancel_requested = Column(Boolean, nullable=False, default=False)

    provider_request_id = Column(String(255), nullable=True)
    polling_url = Column(String(1024), nullable=True)
    error_code = Column(String(64), nullable=True)
    error_message = Column(Text, nullable=True)
    output_asset_ids = Column(JSON, nullable=False, default=list)
    estimated_cost_usd = Column(Float, nullable=True)
    actual_cost_usd = Column(Float, nullable=True)

    created_at = Column(UTCDateTime(), default=_now, nullable=False)
    updated_at = Column(UTCDateTime(), default=_now, onupdate=_now, nullable=False)
    started_at = Column(UTCDateTime(), nullable=True)
    submitted_at = Column(UTCDateTime(), nullable=True)
    finished_at = Column(UTCDateTime(), nullable=True)

    project = relationship("Project", back_populates="jobs")

    __table_args__ = (Index("ix_generation_jobs_status_next", "status", "next_attempt_at"),)


class PromptTemplate(Base):
    """Append-only override history. project_id NULL = global override; body NULL = reset to inherited."""

    __tablename__ = "prompt_templates"

    id = Column(String(36), primary_key=True, default=_uuid)
    name = Column(String(32), nullable=False)
    project_id = Column(String(36), ForeignKey("projects.id", ondelete="CASCADE"), nullable=True)
    body = Column(Text, nullable=True)
    template_version = Column(Integer, nullable=False)
    revision = Column(Integer, nullable=False)
    created_at = Column(UTCDateTime(), default=_now, nullable=False)

    __table_args__ = (Index("ix_prompt_templates_lookup", "name", "project_id", "revision"),)


class MasterVersion(Base):
    __tablename__ = "master_versions"

    id = Column(String(36), primary_key=True, default=_uuid)
    project_id = Column(String(36), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    job_id = Column(String(36), ForeignKey("generation_jobs.id", ondelete="CASCADE"), nullable=False)
    round = Column(Integer, nullable=False)
    variant = Column(Integer, nullable=False)
    created_at = Column(UTCDateTime(), default=_now, nullable=False)

    job = relationship("GenerationJob")


class TurnaroundVersion(Base):
    __tablename__ = "turnaround_versions"

    id = Column(String(36), primary_key=True, default=_uuid)
    project_id = Column(String(36), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    master_version_id = Column(String(36), ForeignKey("master_versions.id", ondelete="CASCADE"), nullable=False)
    forked_from_id = Column(String(36), ForeignKey("turnaround_versions.id", ondelete="SET NULL"), nullable=True)
    number = Column(Integer, nullable=False)
    approved_at = Column(UTCDateTime(), nullable=True)
    created_at = Column(UTCDateTime(), default=_now, nullable=False)

    views = relationship(
        "TurnaroundView", back_populates="version", cascade="all, delete-orphan", order_by="TurnaroundView.created_at"
    )


class TurnaroundView(Base):
    __tablename__ = "turnaround_views"

    id = Column(String(36), primary_key=True, default=_uuid)
    turnaround_version_id = Column(
        String(36), ForeignKey("turnaround_versions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    angle = Column(String(16), nullable=False)
    job_id = Column(String(36), ForeignKey("generation_jobs.id", ondelete="CASCADE"), nullable=False)
    selected = Column(Boolean, nullable=False, default=False)
    created_at = Column(UTCDateTime(), default=_now, nullable=False)

    version = relationship("TurnaroundVersion", back_populates="views")
    job = relationship("GenerationJob")


class ApprovalEvent(Base):
    __tablename__ = "approval_events"

    id = Column(String(36), primary_key=True, default=_uuid)
    project_id = Column(String(36), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    target_type = Column(String(16), nullable=False)  # "master" | "turnaround"
    target_id = Column(String(36), nullable=False)
    previous_id = Column(String(36), nullable=True)
    created_at = Column(UTCDateTime(), default=_now, nullable=False)


class Concept(Base):
    """One standalone slot revision. Earlier results are never overwritten."""

    __tablename__ = "concepts"

    id = Column(String(36), primary_key=True, default=_uuid)
    project_id = Column(String(36), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    run = Column(Integer, nullable=False)
    slot = Column(Integer, nullable=False)
    revision = Column(Integer, nullable=False, default=1)
    mood = Column(String(128), nullable=False)
    camera = Column(String(128), nullable=False)
    brief = Column(JSON, nullable=False)
    master_version_id = Column(String(36), ForeignKey("master_versions.id", ondelete="CASCADE"), nullable=False)
    turnaround_version_id = Column(String(36), ForeignKey("turnaround_versions.id", ondelete="SET NULL"), nullable=True)
    job_id = Column(String(36), ForeignKey("generation_jobs.id", ondelete="CASCADE"), nullable=False)
    created_at = Column(UTCDateTime(), default=_now, nullable=False)

    job = relationship("GenerationJob")


class Preset(Base):
    """A reusable per-step choice of provider, model and size, shared by every project."""

    __tablename__ = "presets"

    id = Column(String(36), primary_key=True, default=_uuid)
    name = Column(String(120), nullable=False)
    # {step: {"provider": ..., "model": ..., "size": ...}} for master/turnaround/concept/enhance.
    steps = Column(JSON, nullable=False, default=dict)
    created_at = Column(UTCDateTime(), default=_now, nullable=False)
    updated_at = Column(UTCDateTime(), default=_now, onupdate=_now, nullable=False)


class ConceptProposal(Base):
    """One model-proposed concept brief, awaiting the user's choice to render it."""

    __tablename__ = "concept_proposals"

    id = Column(String(36), primary_key=True, default=_uuid)
    project_id = Column(String(36), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    master_version_id = Column(String(36), ForeignKey("master_versions.id", ondelete="CASCADE"), nullable=False)
    run = Column(Integer, nullable=False)
    slot = Column(Integer, nullable=False)
    title = Column(String(255), nullable=False)
    brief = Column(JSON, nullable=False)
    created_at = Column(UTCDateTime(), default=_now, nullable=False)


class EnhancementVersion(Base):
    __tablename__ = "enhancement_versions"

    id = Column(String(36), primary_key=True, default=_uuid)
    project_id = Column(String(36), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    concept_id = Column(String(36), ForeignKey("concepts.id", ondelete="CASCADE"), nullable=False, index=True)
    number = Column(Integer, nullable=False)
    master_version_id = Column(String(36), ForeignKey("master_versions.id", ondelete="CASCADE"), nullable=False)
    turnaround_version_id = Column(String(36), ForeignKey("turnaround_versions.id", ondelete="SET NULL"), nullable=True)
    job_id = Column(String(36), ForeignKey("generation_jobs.id", ondelete="CASCADE"), nullable=False)
    created_at = Column(UTCDateTime(), default=_now, nullable=False)

    job = relationship("GenerationJob")


class ProviderCatalog(Base):
    """A provider's model list as fetched from that provider's own API, so it survives restarts."""

    __tablename__ = "provider_catalogs"

    provider = Column(String(32), primary_key=True)
    items = Column(JSON, nullable=False, default=list)  # [{"id": ..., "display_name": ...}]
    source = Column(String(32), nullable=False)
    fetched_at = Column(UTCDateTime(), default=_now, nullable=False)
