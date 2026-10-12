"""Exercise the hybrid routing with offline substitutes, never paid API calls."""
import pytest

from app.main import app
from app.providers.mock import MockProvider
from tests.conftest import wait_for_job


class OfflinePaidProvider(MockProvider):
    def __init__(self, real):
        super().__init__(delay_seconds=0)
        self.name = real.name
        self.models = real.models
        self.estimate_request_cost_usd = real.estimate_request_cost_usd


def test_hybrid_end_to_end_routing_estimates_and_fallback(client, project, reference_ids, monkeypatch):
    for name in ("gemini", "bfl"):
        monkeypatch.setitem(app.state.registry._providers, name, OfflinePaidProvider(app.state.registry.get(name)))
    base = f"/api/projects/{project}"
    updated = client.patch(base, json={"workflow_mode": "hybrid"})
    assert updated.status_code == 200
    assert updated.json()["provider"] == "mock"  # Manual configuration is preserved.
    assert client.get(base).json()["workflow_mode"] == "hybrid"
    estimate = client.get(f"{base}/generation-estimate?purpose=master").json()
    assert estimate["per_image_usd"] == pytest.approx(0.0336)
    response = client.post(f"{base}/master/generate", json={})
    assert response.status_code == 201, response.text
    master_job = wait_for_job(client, response.json()["job_ids"][0])
    assert master_job["status"] == "succeeded"
    assert (master_job["provider"], master_job["model"], master_job["settings"]["size"]) == (
        "gemini", "gemini-nano-banana-2.1", "1K")
    master = client.get(f"{base}/workflow").json()["masters"][0]
    client.post(f"{base}/master/{master['id']}/approve")
    # Hybrid mode must still require confirmation for paid runs.
    assert client.post(f"{base}/turnaround/generate", json={}).status_code == 400
    assert not client.get(f"{base}/workflow").json()["turnarounds"]
    response = client.post(f"{base}/turnaround/generate", json={"confirmed": True})
    assert response.status_code == 201, response.text
    turn = response.json()
    for job_id in turn["job_ids"]:
        job = wait_for_job(client, job_id)
        assert job["status"] == "succeeded"
        assert job["provider"] == "gemini" and job["settings"]["size"] == "1K"
    client.post(f"{base}/turnaround/{turn['id']}/approve")
    # Proposals are rendered in whatever groups the user picks.
    proposals = client.post(f"{base}/concept-proposals").json()
    assert len(proposals) == 9
    for chosen, count in ((proposals[:5], 5), (proposals[5:], 4)):
        response = client.post(f"{base}/concepts/generate",
                               json={"proposal_ids": [p["id"] for p in chosen], "confirmed": True})
        assert response.status_code == 201, response.text
        assert len(response.json()["job_ids"]) == count
        for job_id in response.json()["job_ids"]:
            job = wait_for_job(client, job_id)
            assert job["status"] == "succeeded"
            assert job["provider"] == "gemini" and len(job["reference_asset_ids"]) == 2
    concept = client.get(f"{base}/concepts").json()[0]
    path = f"{base}/concepts/{concept['id']}"
    plan = client.get(f"{path}/enhance-plan").json()
    assert (plan["provider"], plan["model"], plan["size"]) == ("bfl", "flux-2-pro", "1MP")
    assert plan["reference_asset_ids"] == [concept["job"]["output_asset_ids"][0]]
    assert plan["estimated_cost_usd"] == pytest.approx(0.045)
    assert not plan["warning"]
    response = client.post(f"{path}/enhance", json={})
    assert response.status_code == 201, response.text
    job = wait_for_job(client, response.json()["job_ids"][0])
    assert job["status"] == "succeeded"
    assert job["provider"] == "bfl" and job["settings"]["size"] == "1MP"
    assert job["reference_asset_ids"] == plan["reference_asset_ids"]
    assert job["estimated_cost_usd"] == plan["estimated_cost_usd"]
    client.patch(base, json={"workflow_mode": "hybrid_gemini"})
    response = client.post(f"{path}/enhance", json={"size": "2K"})
    assert response.status_code == 201, response.text
    fallback = wait_for_job(client, response.json()["job_ids"][0])
    assert fallback["provider"] == "gemini" and fallback["settings"]["size"] == "2K"
    assert len(fallback["reference_asset_ids"]) == 1
    client.patch(base, json={"workflow_mode": "manual"})
    response = client.post(f"{path}/enhance", json={})
    manual = wait_for_job(client, response.json()["job_ids"][0])
    assert manual["provider"] == "mock" and len(manual["reference_asset_ids"]) == 1


def test_hybrid_missing_key_and_invalid_size_are_atomic(client, project, reference_ids):
    base = f"/api/projects/{project}"
    assert client.patch(base, json={"workflow_mode": "unknown"}).status_code == 422
    client.patch(base, json={"workflow_mode": "hybrid"})
    response = client.post(f"{base}/master/generate", json={})
    assert response.status_code == 400
    assert response.json()["detail"]["code"] == "provider_not_configured"
    assert not client.get(f"{base}/workflow").json()["masters"]
    response = client.get(f"{base}/generation-estimate?purpose=master&size=1MP")
    assert response.status_code == 400
    assert response.json()["detail"]["code"] == "unsupported_size"
