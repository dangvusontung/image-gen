from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.config import JOB_MAX_ATTEMPTS, SPEND_LIMIT_USD_PER_DAY
from app.models import Asset, GenerationJob, JobStatus, Project
from app.providers.base import CapabilityError
from app.providers.registry import ProviderRegistry


class JobRequestError(Exception):
    def __init__(self, code: str, message: str, status: int = 400):
        super().__init__(message)
        self.code, self.message, self.status = code, message, status


def spent_last_24h(db: Session, exclude_ids: list[str] | None = None) -> float:
    since = datetime.now(timezone.utc) - timedelta(hours=24)
    total = (
        db.query(func.coalesce(func.sum(func.coalesce(GenerationJob.actual_cost_usd, GenerationJob.estimated_cost_usd)), 0.0))
        .filter(GenerationJob.created_at >= since)
        .filter(GenerationJob.provider != "mock")
        .filter(GenerationJob.id.notin_(exclude_ids or []))
        # Jobs cancelled or failed before reaching the provider cost nothing.
        .filter(~((GenerationJob.status.in_([JobStatus.CANCELLED, JobStatus.FAILED])) & (GenerationJob.submitted_at.is_(None))))
        .scalar()
    )
    return float(total or 0.0)


def check_spend(db: Session, additional_usd: float, limit: float = SPEND_LIMIT_USD_PER_DAY, exclude_ids: list[str] | None = None) -> None:
    if limit <= 0 or additional_usd <= 0:
        return
    spent = spent_last_24h(db, exclude_ids)
    if spent + additional_usd > limit:
        raise JobRequestError(
            "spend_limit_exceeded",
            f"Vượt giới hạn chi tiêu 24h: đã dùng ~${spent:.2f} + ước tính ${additional_usd:.2f} > ${limit:.2f} "
            "(chỉnh SPEND_LIMIT_USD_PER_DAY trong .env)",
            status=402,
        )


def estimate_job_cost(db, provider, model, reference_asset_ids, size=None):
    refs = db.query(Asset).filter(Asset.id.in_(reference_asset_ids)).all()
    return provider.estimate_request_cost_usd(model, size, [(a.width or 2048, a.height or 2048) for a in refs])


def enqueue_job(
    db: Session,
    registry: ProviderRegistry,
    project: Project,
    *,
    purpose: str,
    prompt: str,
    reference_asset_ids: list[str],
    aspect_ratio: str | None = None,
    size: str | None = None,
    seed: int | None = None,
    options: dict[str, Any] | None = None,
    meta: dict[str, Any] | None = None,
    provider_name: str | None = None,
    model_id: str | None = None,
    skip_spend_check: bool = False,
) -> GenerationJob:
    """Validate everything that can be checked offline, then persist a queued job. Does not commit."""
    if not project.rights_confirmed:
        raise JobRequestError("rights_not_confirmed", "Cần xác nhận quyền sử dụng ảnh trước khi tạo ảnh", 403)

    provider_name = provider_name or project.provider
    model_id = model_id or (project.model if provider_name == project.provider else None)
    try:
        provider = registry.get(provider_name)
        model_id = model_id or provider.default_model().id
        aspect_ratio = aspect_ratio or provider.get_model(model_id).default_aspect_ratio
        model = provider.check_request(model_id, len(reference_asset_ids), aspect_ratio, size)
    except CapabilityError as exc:
        raise JobRequestError(exc.code, exc.message) from None

    if len(set(reference_asset_ids)) != len(reference_asset_ids):
        raise JobRequestError("duplicate_reference", "Ảnh tham chiếu bị lặp")
    found = {
        a.id
        for a in db.query(Asset.id).filter(Asset.id.in_(reference_asset_ids), Asset.project_id == project.id)
    }
    missing = [i for i in reference_asset_ids if i not in found]
    if missing:
        raise JobRequestError("reference_not_found", f"Không tìm thấy {len(missing)} ảnh tham chiếu trong dự án")

    estimate = estimate_job_cost(db, provider, model, reference_asset_ids, size)
    if not skip_spend_check and provider_name != "mock":
        check_spend(db, estimate or 0.0)

    settings: dict[str, Any] = {"aspect_ratio": aspect_ratio, "options": options or {}}
    if size:
        settings["size"] = size
    if seed is not None:
        settings["seed"] = seed

    job = GenerationJob(
        project_id=project.id,
        purpose=purpose,
        provider=provider_name,
        model=model.id,
        prompt=prompt,
        settings=settings,
        reference_asset_ids=list(reference_asset_ids),
        meta=meta or {},
        status=JobStatus.QUEUED,
        max_attempts=JOB_MAX_ATTEMPTS,
        estimated_cost_usd=estimate,
        output_asset_ids=[],
    )
    db.add(job)
    project.updated_at = datetime.now(timezone.utc)
    return job


def request_cancel(db: Session, job: GenerationJob) -> GenerationJob:
    if job.status in JobStatus.FINAL:
        raise JobRequestError("job_finished", "Job đã kết thúc, không huỷ được", 409)
    now = datetime.now(timezone.utc)
    if job.status == JobStatus.QUEUED:
        job.status, job.finished_at = JobStatus.CANCELLED, now
        job.error_code, job.error_message = "cancelled", "Đã huỷ trước khi gửi tới nhà cung cấp"
    else:
        # Already at the provider: stop waiting and ignore the result; it may still be billed.
        job.cancel_requested = True
    return job


def retry_job(db: Session, registry: ProviderRegistry, job: GenerationJob) -> GenerationJob:
    """Manual retry creates a fresh job so history (and any billed attempt) stays visible."""
    if job.status not in (JobStatus.FAILED, JobStatus.CANCELLED):
        raise JobRequestError("job_not_retryable", "Chỉ thử lại được job đã lỗi hoặc đã huỷ", 409)
    project = db.get(Project, job.project_id)
    new_job = enqueue_job(
        db,
        registry,
        project,
        purpose=job.purpose,
        prompt=job.prompt,
        reference_asset_ids=list(job.reference_asset_ids),
        aspect_ratio=job.settings.get("aspect_ratio"),
        size=job.settings.get("size"),
        seed=job.settings.get("seed"),
        options=job.settings.get("options"),
        meta={**job.meta, "retry_of": job.id},
        provider_name=job.provider,
        model_id=job.model,
    )
    from app.jobs.versioning import attach_retry
    attach_retry(db, job, new_job)
    return new_job
