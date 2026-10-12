import asyncio
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from app.database import SessionLocal
from app.jobs.service import JobRequestError, check_spend


def test_zero_spend_limit_disables_cap():
    # Unlimited requests should not query spend or reject the generation.
    check_spend(None, 10000, limit=0)
from app.main import app
from app.models import GenerationJob, JobStatus
from app.providers.base import ImageRequest, Submission, SubmissionState
from app.providers.mock import MockProvider
from tests.conftest import make_image, wait_for_job


def test_job_succeeds_and_stores_generated_asset(client, project, enqueue):
    job_id = enqueue(aspect_ratio="3:4")
    job = wait_for_job(client, job_id)
    assert job["status"] == "succeeded", job
    assert job["provider"] == "mock" and job["model"] == "mock-v1"
    assert job["attempts"] == 1 and job["provider_request_id"].startswith("mock-")
    assert job["estimated_cost_usd"] == 0.0 and job["submitted_at"] and job["finished_at"]
    [asset_id] = job["output_asset_ids"]

    content = client.get(f"/api/assets/{asset_id}/content")
    assert content.status_code == 200 and content.headers["content-type"] == "image/png"
    # Generated outputs are not source photos and can't be deleted via the references UI.
    assert asset_id not in [a["id"] for a in client.get(f"/api/projects/{project}").json()["assets"]]
    assert client.delete(f"/api/assets/{asset_id}").json()["detail"]["code"] == "asset_not_editable"

    listed = client.get(f"/api/projects/{project}/jobs").json()
    assert [j["id"] for j in listed] == [job_id]


def test_enqueue_validates_offline(client, project, enqueue, reference_ids):
    with pytest.raises(JobRequestError) as exc:
        enqueue(model_id="mock-small-refs")
    assert exc.value.code == "reference_limit_exceeded"
    with pytest.raises(JobRequestError) as exc:
        enqueue(aspect_ratio="7:3")
    assert exc.value.code == "unsupported_aspect_ratio"
    with pytest.raises(JobRequestError) as exc:
        enqueue(reference_asset_ids=["missing"])
    assert exc.value.code == "reference_not_found"
    with pytest.raises(JobRequestError) as exc:
        enqueue(provider_name="gemini")
    assert exc.value.code == "provider_not_configured"
    with pytest.raises(JobRequestError) as exc:
        enqueue(provider_name="midjourney")
    assert exc.value.code == "provider_disabled"

    client.patch(f"/api/projects/{project}", json={"rights_confirmed": False})
    with pytest.raises(JobRequestError) as exc:
        enqueue()
    assert exc.value.code == "rights_not_confirmed"


def test_transient_errors_retry_with_backoff_then_succeed(client, enqueue):
    job = wait_for_job(client, enqueue(options={"mock": "transient:2", "mock_key": "a"}))
    assert job["status"] == "succeeded" and job["attempts"] == 3


def test_transient_errors_give_up_after_max_attempts(client, enqueue):
    job = wait_for_job(client, enqueue(options={"mock": "transient:9", "mock_key": "b"}))
    assert job["status"] == "failed" and job["attempts"] == 3
    assert job["error_code"] == "rate_limited" and "đã thử 3 lần" in job["error_message"]


def test_ambiguous_submit_is_not_retried(client, enqueue):
    job = wait_for_job(client, enqueue(options={"mock": "ambiguous"}))
    assert job["status"] == "failed" and job["attempts"] == 1
    assert "tính phí hai lần" in job["error_message"]


def test_one_failure_does_not_affect_other_jobs(client, enqueue):
    ids = [enqueue(), enqueue(options={"mock": "fail"}), enqueue(), enqueue(options={"mock": "moderated"}), enqueue()]
    results = [wait_for_job(client, i) for i in ids]
    assert [r["status"] for r in results] == ["succeeded", "failed", "succeeded", "failed", "succeeded"]
    assert results[3]["error_code"] == "content_moderated"


def test_concurrency_is_bounded(client, enqueue):
    class CountingMock(MockProvider):
        active = peak = 0

        async def submit(self, request):
            CountingMock.active += 1
            CountingMock.peak = max(CountingMock.peak, CountingMock.active)
            return await super().submit(request)

        async def poll(self, submission):
            result = await super().poll(submission)
            if result.state == SubmissionState.READY:
                CountingMock.active -= 1
            return result

    app.state.registry._providers["mock"] = CountingMock(delay_seconds=0.3)
    ids = [enqueue() for _ in range(5)]
    assert all(wait_for_job(client, i)["status"] == "succeeded" for i in ids)
    assert CountingMock.peak == 2  # JOB_CONCURRENCY in conftest


def test_cancel_queued_and_running(client, enqueue):
    app.state.registry._providers["mock"] = MockProvider(delay_seconds=5)
    running = enqueue()
    wait_for_job(client, running, statuses={"running"})
    resp = client.post(f"/api/jobs/{running}/cancel")
    assert resp.status_code == 200 and resp.json()["cancel_requested"] is True
    job = wait_for_job(client, running)
    assert job["status"] == "cancelled" and "có thể vẫn tính phí" in job["error_message"]
    assert client.post(f"/api/jobs/{running}/cancel").status_code == 409

    with SessionLocal() as db:  # a job scheduled for a later retry is still "queued"
        queued = GenerationJob(
            project_id=job["project_id"], purpose="test", provider="mock", model="mock-v1", prompt="x",
            settings={}, reference_asset_ids=[], meta={}, status=JobStatus.QUEUED, output_asset_ids=[],
            next_attempt_at=datetime.now(timezone.utc) + timedelta(hours=1),
        )
        db.add(queued)
        db.commit()
        queued_id = queued.id
    resp = client.post(f"/api/jobs/{queued_id}/cancel")
    assert resp.json()["status"] == "cancelled"


def test_manual_retry_creates_new_job_and_keeps_history(client, project, enqueue):
    failed = wait_for_job(client, enqueue(options={"mock": "fail"}))
    assert client.post(f"/api/jobs/{failed['id']}/retry").status_code == 201
    jobs = client.get(f"/api/projects/{project}/jobs").json()
    assert len(jobs) == 2
    new = next(j for j in jobs if j["id"] != failed["id"])
    assert new["meta"]["retry_of"] == failed["id"]
    assert new["reference_asset_ids"] == failed["reference_asset_ids"]
    assert client.get(f"/api/jobs/{failed['id']}").json()["status"] == "failed"
    # The retry carries the same failing option, so it fails too — but independently.
    assert wait_for_job(client, new["id"])["status"] == "failed"


def test_jobs_survive_restart(client, project, enqueue):
    app.state.registry._providers["mock"] = MockProvider(delay_seconds=30)
    running = enqueue()
    wait_for_job(client, running, statuses={"running"})

    with SessionLocal() as db:
        interrupted = GenerationJob(
            project_id=project, purpose="test", provider="mock", model="mock-v1", prompt="x", settings={},
            reference_asset_ids=[], meta={}, status=JobStatus.SUBMITTING, attempts=1, output_asset_ids=[],
        )
        db.add(interrupted)
        db.commit()
        interrupted_id = interrupted.id

    client.__exit__(None, None, None)  # stop the app (runner) mid-job
    with TestClient(app) as restarted:  # fresh registry: the old in-memory mock task is gone
        resumed = wait_for_job(restarted, running)
        assert resumed["status"] == "succeeded" and resumed["attempts"] == 1
        lost = restarted.get(f"/api/jobs/{interrupted_id}").json()
        assert lost["status"] == "failed" and lost["error_code"] == "interrupted"


def test_spend_guard_counts_paid_jobs_in_last_24h(client, project):
    with SessionLocal() as db:
        for status, submitted in ((JobStatus.SUCCEEDED, True), (JobStatus.FAILED, False)):
            db.add(GenerationJob(
                project_id=project, purpose="test", provider="gemini", model="m", prompt="x", settings={},
                reference_asset_ids=[], meta={}, status=status, output_asset_ids=[], estimated_cost_usd=0.6,
                submitted_at=datetime.now(timezone.utc) if submitted else None,
            ))
        db.commit()
        check_spend(db, 0.3)  # 0.6 counted (failed-before-submit is free) + 0.3 <= 1.0
        with pytest.raises(JobRequestError) as exc:
            check_spend(db, 0.5)
        assert exc.value.code == "spend_limit_exceeded" and exc.value.status == 402
    spend = client.get("/api/spend").json()
    assert spend == {"spent_24h_usd": 0.6, "limit_usd": 1.0}


def test_deleting_project_while_job_runs_is_safe(client, project, enqueue):
    app.state.registry._providers["mock"] = MockProvider(delay_seconds=0.3)
    job_id = enqueue()
    wait_for_job(client, job_id, statuses={"running"})
    assert client.delete(f"/api/projects/{project}").status_code == 204
    assert client.get(f"/api/jobs/{job_id}").status_code == 404
    asyncio.run(asyncio.sleep(0.6))
    assert app.state.runner.inflight_count == 0


def test_mock_request_dataclass_roundtrip():
    sub = Submission(SubmissionState.PENDING, "id", "mock://id")
    assert ImageRequest(model="m", prompt="p").aspect_ratio == "1:1" and sub.images == []


def test_global_history_lists_every_project_with_its_name(client, project, reference_ids):
    other = client.post("/api/projects", json={"name": "Dự án khác"}).json()["id"]
    client.patch(f"/api/projects/{other}", json={"rights_confirmed": True})
    files = [("files", ("r.png", make_image(), "image/png"))]
    client.post(f"/api/projects/{other}/assets", files=files)
    for pid in (project, other):
        assert client.post(f"/api/projects/{pid}/master/generate", json={}).status_code == 201

    history = client.get("/api/jobs?limit=50").json()
    assert {row["project_name"] for row in history} == {"Dự án thử", "Dự án khác"}
    assert all(row["purpose"] == "master" and row["project_id"] for row in history)
    # Newest first, so the popup opens on what just happened.
    assert [r["created_at"] for r in history] == sorted((r["created_at"] for r in history), reverse=True)
    assert client.get("/api/jobs?purpose=enhance").json() == []
    assert len(client.get("/api/jobs?limit=1").json()) == 1
