import uuid
from datetime import datetime, timezone

from sqlalchemy import JSON, Boolean, Column, Float, ForeignKey, Index, Integer, String, Text, and_
from sqlalchemy.orm import foreign, relationship

from app.database import Base, UTCDateTime

SOURCE_KINDS = ("reference", "side_profile")


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
    created_at = Column(UTCDateTime(), default=_now, nullable=False)
    updated_at = Column(UTCDateTime(), default=_now, onupdate=_now, nullable=False)

    assets = relationship("Asset", back_populates="project", cascade="all, delete-orphan", order_by="Asset.position")
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
