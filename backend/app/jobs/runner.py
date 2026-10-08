import asyncio
import logging
import random
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Callable

from sqlalchemy import or_, update
from sqlalchemy.orm import Session

from app.config import GENERATED_MAX_SIZE
from app.models import Asset, GenerationJob, JobStatus, Project
from app.providers.base import (
    ErrorKind,
    ImageProvider,
    ImageRequest,
    ProviderError,
    ReferenceImage,
    Submission,
    SubmissionState,
)
from app.providers.registry import ProviderRegistry
from app.storage.images import prepare_reference
from app.storage.local import LocalStorage
from app.storage.validation import InvalidImage, validate_image

log = logging.getLogger("app.jobs")

_MAX_POLL_ERRORS = 5
_AMBIGUOUS_HINT = " — không tự gửi lại để tránh bị tính phí hai lần; hãy kiểm tra rồi thử lại thủ công."


def _now() -> datetime:
    return datetime.now(timezone.utc)


@dataclass
class _Snapshot:
    id: str
    project_id: str
    purpose: str
    provider: str
    model: str
    prompt: str
    settings: dict[str, Any]
    reference_asset_ids: list[str]
    meta: dict[str, Any]
    provider_request_id: str | None
    polling_url: str | None
    submitted_at: datetime | None


class JobRunner:
    """In-process async worker. Assumes a single backend process owns the database."""

    def __init__(
        self,
        session_factory: Callable[[], Session],
        registry: ProviderRegistry,
        storage: LocalStorage,
        *,
        concurrency: int,
        backoff_base: float,
        poll_interval: float,
        poll_timeout: float,
        tick: float = 1.0,
    ):
        self._sessions = session_factory
        self._registry = registry
        self._storage = storage
        self._concurrency = max(1, concurrency)
        self._backoff_base = backoff_base
        self._poll_interval = poll_interval
        self._poll_timeout = poll_timeout
        self._tick = tick
        self._inflight: dict[str, asyncio.Task] = {}
        self._loop: asyncio.AbstractEventLoop | None = None
        self._wake: asyncio.Event | None = None
        self._main: asyncio.Task | None = None

    # ---- lifecycle -------------------------------------------------------------------------

    async def start(self) -> None:
        self._loop = asyncio.get_running_loop()
        self._wake = asyncio.Event()
        self.recover()
        self._main = asyncio.create_task(self._run_loop(), name="job-runner")

    async def stop(self) -> None:
        tasks = [t for t in (self._main, *self._inflight.values()) if t]
        for t in tasks:
            t.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        self._inflight.clear()
        self._loop = None

    def notify(self) -> None:
        """Wake the dispatcher; safe to call from request-handler threads."""
        if self._loop and self._wake and not self._loop.is_closed():
            self._loop.call_soon_threadsafe(self._wake.set)

    def recover(self) -> None:
        with self._sessions() as db:
            for job in db.query(GenerationJob).filter(GenerationJob.status.in_([JobStatus.SUBMITTING, JobStatus.RUNNING])):
                if job.provider_request_id and job.polling_url:
                    job.status = JobStatus.RUNNING
                    log.info("job %s: resuming polling for %s", job.id, job.provider_request_id)
                else:
                    self._set_failed(job, ProviderError(
                        "interrupted",
                        "Máy chủ dừng khi đang gửi yêu cầu, không rõ nhà cung cấp đã nhận chưa" + _AMBIGUOUS_HINT,
                        ErrorKind.AMBIGUOUS,
                    ))
            db.commit()

    @property
    def inflight_count(self) -> int:
        return len(self._inflight)

    # ---- dispatch --------------------------------------------------------------------------

    async def _run_loop(self) -> None:
        assert self._wake is not None
        while True:
            try:
                self._dispatch()
            except Exception:
                log.exception("job dispatcher error")
            try:
                await asyncio.wait_for(self._wake.wait(), timeout=self._tick)
            except TimeoutError:
                pass
            self._wake.clear()

    def _spawn(self, job_id: str, coro) -> None:
        task = asyncio.create_task(coro, name=f"job-{job_id}")
        self._inflight[job_id] = task

        def _done(t: asyncio.Task) -> None:
            self._inflight.pop(job_id, None)
            if not t.cancelled() and t.exception():
                log.error("job %s crashed: %r", job_id, t.exception())
                self._fail_unexpected(job_id)
            self.notify()

        task.add_done_callback(_done)

    def _dispatch(self) -> None:
        free = self._concurrency - len(self._inflight)
        if free <= 0:
            return
        with self._sessions() as db:
            running = (
                db.query(GenerationJob.id)
                .filter(GenerationJob.status == JobStatus.RUNNING, GenerationJob.id.notin_(list(self._inflight)))
                .order_by(GenerationJob.submitted_at)
                .limit(free)
                .all()
            )
            for (job_id,) in running:
                self._spawn(job_id, self._resume(job_id))
            free -= len(running)
            if free <= 0:
                return

            now = _now()
            due = (
                db.query(GenerationJob.id)
                .filter(GenerationJob.status == JobStatus.QUEUED)
                .filter(or_(GenerationJob.next_attempt_at.is_(None), GenerationJob.next_attempt_at <= now))
                .order_by(GenerationJob.created_at)
                .limit(free)
                .all()
            )
            for (job_id,) in due:
                claimed = db.execute(
                    update(GenerationJob)
                    .where(GenerationJob.id == job_id, GenerationJob.status == JobStatus.QUEUED)
                    .values(status=JobStatus.SUBMITTING, attempts=GenerationJob.attempts + 1, updated_at=now)
                ).rowcount
                db.commit()
                if claimed:
                    self._spawn(job_id, self._execute(job_id))

    # ---- job execution ---------------------------------------------------------------------

    def _snapshot(self, job_id: str) -> _Snapshot | None:
        with self._sessions() as db:
            job = db.get(GenerationJob, job_id)
            if job is None:
                return None
            if job.started_at is None:
                job.started_at = _now()
                db.commit()
            return _Snapshot(
                job.id, job.project_id, job.purpose, job.provider, job.model, job.prompt, dict(job.settings),
                list(job.reference_asset_ids), dict(job.meta), job.provider_request_id, job.polling_url, job.submitted_at,
            )

    def _load_references(self, snap: _Snapshot) -> list[ReferenceImage]:
        with self._sessions() as db:
            assets = {a.id: a for a in db.query(Asset).filter(Asset.id.in_(snap.reference_asset_ids))}
            refs = []
            for index, asset_id in enumerate(snap.reference_asset_ids, start=1):
                asset = assets.get(asset_id)
                if asset is None:
                    raise ProviderError("reference_missing", "Một ảnh tham chiếu đã bị xoá trước khi job chạy")
                try:
                    raw = self._storage.path_for(asset.file_path).read_bytes()
                except (FileNotFoundError, ValueError):
                    raise ProviderError("reference_missing", f"File ảnh tham chiếu {asset.filename} không còn trên đĩa") from None
                try:
                    data, mime = prepare_reference(raw)
                except OSError:
                    raise ProviderError("reference_invalid", f"Không đọc được ảnh tham chiếu {asset.filename}") from None
                labels = snap.meta.get("reference_labels") or []
                if index <= len(labels):
                    label = labels[index - 1]
                else:
                    kind = {"reference": "reference photo", "side_profile": "side profile photo"}.get(asset.kind, asset.kind)
                    label = f"{kind} {index}"
                refs.append(ReferenceImage(data=data, mime_type=mime, label=label))
            return refs

    async def _execute(self, job_id: str) -> None:
        snap = self._snapshot(job_id)
        if snap is None:
            return
        if self._is_cancel_requested(job_id):
            self._finalize_cancelled(job_id, "Đã huỷ trước khi gửi tới nhà cung cấp")
            return
        try:
            provider = self._registry.get(snap.provider)
            refs = await asyncio.to_thread(self._load_references, snap)
            request = ImageRequest(
                model=snap.model,
                prompt=snap.prompt,
                references=refs,
                aspect_ratio=snap.settings.get("aspect_ratio", "1:1"),
                seed=snap.settings.get("seed"),
                options={**snap.settings.get("options", {}), **({"size": snap.settings["size"]} if snap.settings.get("size") else {})},
            )
            provider.validate(request)
            log.info("job %s: submitting to %s/%s with %d references", job_id, snap.provider, snap.model, len(refs))
            # Reserve spend before sending, including sync APIs and unknown outcomes.
            with self._sessions() as db:
                job = db.get(GenerationJob, job_id)
                if job is None:
                    return
                job.submitted_at = _now()
                db.commit()
            submission = await provider.submit(request)
        except ProviderError as exc:
            self._handle_submit_error(job_id, exc)
            return

        if submission.state == SubmissionState.READY:
            await self._complete(job_id, snap, submission)
            return
        self._mark_running(job_id, submission)
        await self._poll_until_done(job_id, snap, provider, submission, started=time.monotonic())

    async def _resume(self, job_id: str) -> None:
        snap = self._snapshot(job_id)
        if snap is None:
            return
        try:
            provider = self._registry.get(snap.provider)
        except ProviderError as exc:
            self._fail(job_id, exc)
            return
        elapsed = (_now() - snap.submitted_at).total_seconds() if snap.submitted_at else 0.0
        submission = Submission(SubmissionState.PENDING, snap.provider_request_id, snap.polling_url)
        await self._poll_until_done(job_id, snap, provider, submission, started=time.monotonic() - elapsed)

    async def _poll_until_done(
        self, job_id: str, snap: _Snapshot, provider: ImageProvider, submission: Submission, started: float
    ) -> None:
        interval, errors = self._poll_interval, 0
        while True:
            if self._is_cancel_requested(job_id):
                self._finalize_cancelled(job_id, "Đã huỷ khi đang chờ kết quả; nhà cung cấp có thể vẫn tính phí")
                return
            if time.monotonic() - started > self._poll_timeout:
                self._fail(job_id, ProviderError(
                    "poll_timeout",
                    f"Quá {self._poll_timeout:.0f}s chưa có kết quả từ nhà cung cấp" + _AMBIGUOUS_HINT,
                    ErrorKind.AMBIGUOUS,
                ))
                return
            await asyncio.sleep(interval)
            try:
                result = await provider.poll(submission)
            except ProviderError as exc:
                # Polling is free to repeat; only give up on permanent errors or a long error streak.
                if exc.kind != ErrorKind.PERMANENT and errors < _MAX_POLL_ERRORS:
                    errors += 1
                    interval = min(max(interval, 1.0) * 2, 30.0)
                    log.warning("job %s: poll error %s (%d/%d)", job_id, exc.code, errors, _MAX_POLL_ERRORS)
                    continue
                self._fail(job_id, exc)
                return
            errors = 0
            if result.state == SubmissionState.READY:
                await self._complete(job_id, snap, result)
                return
            submission = result
            interval = min(interval * 1.5, 5.0)

    async def _complete(self, job_id: str, snap: _Snapshot, submission: Submission) -> None:
        saved: list[tuple[str, Any]] = []
        try:
            for image in submission.images:
                info = await asyncio.to_thread(validate_image, image.data, GENERATED_MAX_SIZE)
                rel = self._storage.save(image.data, snap.project_id, info.ext)
                saved.append((rel, (image.data, info)))
        except InvalidImage as exc:
            self._delete_files([r for r, _ in saved])
            self._fail(job_id, ProviderError("bad_output", f"Ảnh trả về không hợp lệ: {exc}"))
            return
        if not saved:
            self._fail(job_id, ProviderError("no_image", "Nhà cung cấp không trả về ảnh nào"))
            return

        with self._sessions() as db:
            job = db.get(GenerationJob, job_id)
            if job is None:  # project deleted meanwhile
                self._delete_files([r for r, _ in saved])
                return
            if job.cancel_requested:
                self._delete_files([r for r, _ in saved])
                self._set_cancelled(job, "Đã huỷ; kết quả đến sau bị bỏ qua (nhà cung cấp có thể vẫn tính phí)")
                db.commit()
                return
            try:
                asset_ids = []
                for index, (rel, (data, info)) in enumerate(saved):
                    asset = Asset(
                        project_id=snap.project_id,
                        kind="generated",
                        job_id=job_id,
                        filename=f"{snap.purpose}-{job_id[:8]}-{index + 1}.{info.ext}",
                        file_path=rel,
                        size=len(data),
                        content_type=info.content_type,
                        width=info.width,
                        height=info.height,
                        position=index,
                    )
                    db.add(asset)
                    db.flush()
                    asset_ids.append(asset.id)
                job.output_asset_ids = asset_ids
                job.provider_request_id = job.provider_request_id or submission.provider_request_id
                if submission.actual_cost_usd is not None:
                    job.actual_cost_usd = submission.actual_cost_usd
                job.status, job.finished_at = JobStatus.SUCCEEDED, _now()
                job.error_code = job.error_message = None
                project = db.get(Project, snap.project_id)
                if project is not None:
                    project.updated_at = _now()
                db.commit()
            except Exception:
                db.rollback()
                self._delete_files([r for r, _ in saved])
                raise
        log.info("job %s: succeeded (%d image(s))", job_id, len(saved))

    # ---- state transitions -----------------------------------------------------------------

    def _mark_running(self, job_id: str, submission: Submission) -> None:
        with self._sessions() as db:
            job = db.get(GenerationJob, job_id)
            if job is None:
                return
            job.status = JobStatus.RUNNING
            job.provider_request_id = submission.provider_request_id
            job.polling_url = submission.polling_url
            job.submitted_at = _now()
            if submission.actual_cost_usd is not None:
                job.actual_cost_usd = submission.actual_cost_usd
            db.commit()
        log.info("job %s: submitted, provider request %s", job_id, submission.provider_request_id)

    def _handle_submit_error(self, job_id: str, exc: ProviderError) -> None:
        with self._sessions() as db:
            job = db.get(GenerationJob, job_id)
            if job is None:
                return
            if exc.kind != ErrorKind.AMBIGUOUS:
                job.submitted_at = None
            if exc.kind == ErrorKind.TRANSIENT_SAFE and job.attempts < job.max_attempts and not job.cancel_requested:
                delay = max(exc.retry_after or 0.0, self._backoff_base * 2 ** (job.attempts - 1))
                delay *= 1 + random.random() * 0.25
                job.status = JobStatus.QUEUED
                job.next_attempt_at = _now() + timedelta(seconds=delay)
                job.error_code = exc.code
                job.error_message = f"{exc.message} — sẽ thử lại lần {job.attempts + 1}/{job.max_attempts} sau {delay:.0f}s"
                log.warning("job %s: transient %s, retry in %.1fs", job_id, exc.code, delay)
            else:
                if exc.kind == ErrorKind.TRANSIENT_SAFE:
                    exc = ProviderError(exc.code, f"{exc.message} (đã thử {job.attempts} lần)", exc.kind)
                self._set_failed(job, exc)
            db.commit()

    def _fail(self, job_id: str, exc: ProviderError) -> None:
        with self._sessions() as db:
            job = db.get(GenerationJob, job_id)
            if job is not None and job.status not in JobStatus.FINAL:
                self._set_failed(job, exc)
                db.commit()

    def _fail_unexpected(self, job_id: str) -> None:
        try:
            self._fail(job_id, ProviderError("internal_error", "Lỗi nội bộ khi xử lý job" + _AMBIGUOUS_HINT, ErrorKind.AMBIGUOUS))
        except Exception:
            log.exception("job %s: could not record failure", job_id)

    @staticmethod
    def _set_failed(job: GenerationJob, exc: ProviderError) -> None:
        message = exc.message
        if exc.kind == ErrorKind.AMBIGUOUS and _AMBIGUOUS_HINT not in message:
            message += _AMBIGUOUS_HINT
        job.status, job.finished_at = JobStatus.FAILED, _now()
        job.error_code, job.error_message = exc.code, message
        job.next_attempt_at = None
        log.warning("job %s: failed %s", job.id, exc.code)

    @staticmethod
    def _set_cancelled(job: GenerationJob, message: str) -> None:
        job.status, job.finished_at = JobStatus.CANCELLED, _now()
        job.error_code, job.error_message = "cancelled", message

    def _finalize_cancelled(self, job_id: str, message: str) -> None:
        with self._sessions() as db:
            job = db.get(GenerationJob, job_id)
            if job is not None and job.status not in JobStatus.FINAL:
                self._set_cancelled(job, message)
                db.commit()

    def _is_cancel_requested(self, job_id: str) -> bool:
        with self._sessions() as db:
            job = db.get(GenerationJob, job_id)
            return job is None or job.cancel_requested or job.status == JobStatus.CANCELLED

    def _delete_files(self, rel_paths: list[str]) -> None:
        for rel in rel_paths:
            self._storage.delete(rel)
