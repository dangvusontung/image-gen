import io
import json
import zipfile
from dataclasses import replace

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from app.main import app
from app.providers.base import ProviderError
from app.providers.mock import MockProvider
from tests.conftest import wait_for_job


@pytest.fixture()
def studio(client, project, reference_ids):
    base = f"/api/projects/{project}"
    result = client.post(f"{base}/master/generate", json={})
    assert result.status_code == 201, result.text
    wait_for_job(client, result.json()["job_ids"][0])
    master = client.get(f"{base}/workflow").json()["masters"][0]
    assert client.post(f"{base}/master/{master['id']}/approve").status_code == 200
    turn = client.post(f"{base}/turnaround/generate", json={}).json()
    for job_id in turn["job_ids"]:
        assert wait_for_job(client, job_id)["status"] == "succeeded"
    assert client.post(f"{base}/turnaround/{turn['id']}/approve").status_code == 200
    return base, master, turn


def batch(client, base, name):
    response = client.post(f"{base}/concepts/generate", json={"batch": name})
    assert response.status_code == 201, response.text
    for job_id in response.json()["job_ids"]:
        wait_for_job(client, job_id)
    return response.json()


def test_nine_standalone_concepts_enhance_export_and_restart(client, studio):
    base, master, turn = studio
    a = batch(client, base, "A")
    b = batch(client, base, "B")
    assert len(a["job_ids"]) == 5 and len(b["job_ids"]) == 4
    concepts = client.get(f"{base}/concepts").json()
    assert len(concepts) == 9
    assert {c["slot"] for c in concepts} == set(range(1, 10))
    assert len({c["brief"]["setting"] for c in concepts}) == 9
    assert len({c["camera"] for c in concepts}) == 9
    assert len({c["job"]["output_asset_ids"][0] for c in concepts}) == 9
    for c in concepts:
        assert c["job"]["status"] == "succeeded"
        assert set(c["brief"]) == {"setting", "activity", "outfit", "pose", "expression", "gaze", "camera", "lighting"}
        assert c["master_version_id"] == master["id"]
        assert c["turnaround_version_id"] == turn["id"]
        assert len(c["job"]["reference_asset_ids"]) == 7
    c = concepts[0]
    plan = client.get(f"{base}/concepts/{c['id']}/enhance-plan").json()
    assert not plan["warning"]
    assert plan["reference_asset_ids"][:2] == [master["job"]["output_asset_ids"][0], c["job"]["output_asset_ids"][0]]
    result = client.post(f"{base}/concepts/{c['id']}/enhance", json={})
    assert result.status_code == 201, result.text
    enhanced = wait_for_job(client, result.json()["job_ids"][0])
    assert enhanced["status"] == "succeeded"
    assert enhanced["settings"]["aspect_ratio"] == "3:4"
    assert enhanced["output_asset_ids"] != c["job"]["output_asset_ids"]
    assert enhanced["reference_asset_ids"] == plan["reference_asset_ids"]
    asset_id = enhanced["output_asset_ids"][0]
    for fmt in ("original", "png", "jpeg"):
        image = client.get(f"/api/assets/{asset_id}/download?format={fmt}")
        assert image.status_code == 200
        assert 'attachment' in image.headers["content-disposition"]
        with Image.open(io.BytesIO(image.content)) as output:
            assert output.width * 4 == output.height * 3
            assert output.format == ("JPEG" if fmt == "jpeg" else "PNG")
    for name in ("A", "B"):
        sheet = client.get(f"{base}/contact-sheet?batch={name}")
        assert sheet.status_code == 200
        with Image.open(io.BytesIO(sheet.content)) as image:
            assert image.width > 1000 and image.height > 1000
    archive = client.get(f"{base}/export")
    assert archive.status_code == 200
    with zipfile.ZipFile(io.BytesIO(archive.content)) as zipped:
        manifest = json.loads(zipped.read("manifest.json"))
        assert len(manifest["assets"]) == 20  # 3 refs + master + 6 views + 9 concepts + enhancement
        assert "contact-sheet.png" in zipped.namelist()
        assert all(not name.startswith('/') and '..' not in name for name in zipped.namelist())
        assert any(j["purpose"] == "enhance" for j in manifest["jobs"])
    client.__exit__(None, None, None)
    with TestClient(app) as restarted:
        assert len(restarted.get(f"{base}/concepts").json()) == 9
        assert len(restarted.get(f"{base}/enhancements").json()) == 1
        assert restarted.get(f"/api/assets/{asset_id}/content").status_code == 200


def test_one_slot_failure_retry_and_regeneration_keep_successes(client, studio):
    base, _, _ = studio

    class FailOne(MockProvider):
        failed_once = False

        async def submit(self, request):
            if "Mood: Playful & Mischievous" in request.prompt and not self.failed_once:
                self.failed_once = True
                raise ProviderError("test_slot_failure", "One failed slot")
            return await super().submit(request)

    app.state.registry._providers["mock"] = FailOne(delay_seconds=0)
    batch(client, base, "A")
    rows = client.get(f"{base}/concepts").json()
    failed = next(c for c in rows if c["slot"] == 2)
    assert failed["job"]["status"] == "failed"
    successes = {c["slot"]: c["job"]["output_asset_ids"] for c in rows if c["slot"] != 2}
    assert len(successes) == 4 and all(successes.values())
    retry = client.post(f"/api/jobs/{failed['job']['id']}/retry")
    assert retry.status_code == 201
    assert wait_for_job(client, retry.json()["id"])["status"] == "succeeded"
    rows = client.get(f"{base}/concepts").json()
    assert len(rows) == 6
    slot2 = [c for c in rows if c["slot"] == 2]
    assert {c["revision"] for c in slot2} == {1, 2}
    assert slot2[0]["job"]["prompt"] == slot2[1]["job"]["prompt"]
    regenerate = client.post(f"{base}/concepts/{slot2[0]['id']}/regenerate", json={})
    assert regenerate.status_code == 201
    wait_for_job(client, regenerate.json()["job_ids"][0])
    rows = client.get(f"{base}/concepts").json()
    assert len(rows) == 7
    assert {c["slot"]: c["job"]["output_asset_ids"] for c in rows if c["slot"] != 2} == successes
    assert next(c for c in rows if c["revision"] == 3)["brief"]["setting"] != failed["brief"]["setting"]


def test_reference_limit_never_silently_discards_and_enhance_requires_confirmation(client, studio):
    base, master, _ = studio
    batch(client, base, "A")
    concept = client.get(f"{base}/concepts").json()[0]
    client.patch(base, json={"model": "mock-small-refs"})
    before = len(client.get(f"{base}/jobs").json())
    response = client.post(f"{base}/concepts/generate", json={"batch": "B"})
    assert response.status_code == 400 and response.json()["detail"]["code"] == "reference_limit_exceeded"
    assert len(client.get(f"{base}/jobs").json()) == before
    path = f"{base}/concepts/{concept['id']}"
    plan = client.get(f"{path}/enhance-plan").json()
    assert len(plan["reference_asset_ids"]) == 2 and len(plan["omitted_asset_ids"]) == 6
    assert plan["warning"]
    assert plan["reference_asset_ids"][0] == master["job"]["output_asset_ids"][0]
    assert client.post(f"{path}/enhance", json={}).json()["detail"]["code"] == "reference_subset_confirmation_required"
    result = client.post(f"{path}/enhance", json={"confirm_reference_subset": True})
    assert result.status_code == 201
    job = wait_for_job(client, result.json()["job_ids"][0])
    assert job["status"] == "succeeded" and len(job["reference_asset_ids"]) == 2
    assert len(job["meta"]["omitted_asset_ids"]) == 6


def test_bulk_cost_confirmation_and_atomic_spend_guard(client, studio):
    base, _, _ = studio

    class PaidMock(MockProvider):
        name = "paid-test"

        def models(self):
            return [replace(super().models()[0], price_per_image_usd=0.1)]

    app.state.registry._providers["paid-test"] = PaidMock(delay_seconds=10)
    assert client.patch(base, json={"provider": "paid-test", "model": "mock-v1"}).status_code == 200
    before = len(client.get(f"{base}/jobs").json())
    denied = client.post(f"{base}/concepts/generate", json={"batch": "A"})
    assert denied.status_code == 400 and denied.json()["detail"]["code"] == "bulk_confirmation_required"
    assert len(client.get(f"{base}/jobs").json()) == before
    assert client.get(f"{base}/concepts").json() == []
    assert client.post(f"{base}/concepts/generate", json={"batch": "A", "confirmed": True}).status_code == 201
    assert client.post(f"{base}/concepts/generate", json={"batch": "B", "confirmed": True}).status_code == 201
    # 0.5 + 0.4 fits the $1 cap. A further batch must roll back every slot.
    rejected = client.post(f"{base}/concepts/generate", json={"batch": "A", "confirmed": True})
    assert rejected.status_code == 402, rejected.text
    assert len(client.get(f"{base}/concepts").json()) == 9


def test_later_runs_change_camera_assignments_and_new_master_marks_stale(client, studio):
    base, _, _ = studio
    batch(client, base, "A")
    batch(client, base, "A")
    rows = client.get(f"{base}/concepts").json()
    assert len({c["brief"]["setting"] for c in rows}) == 10
    cameras = {(c["run"], c["slot"]): c["camera"] for c in rows}
    assert all(cameras[(1, i)] != cameras[(2, i)] for i in range(1, 6))
    generated = client.post(f"{base}/master/generate", json={}).json()
    wait_for_job(client, generated["job_ids"][0])
    new_master = client.get(f"{base}/workflow").json()["masters"][0]
    client.post(f"{base}/master/{new_master['id']}/approve")
    assert all(c["stale"] for c in client.get(f"{base}/concepts").json())


def test_exports_validation_and_project_isolation(client, studio):
    base, _, _ = studio
    assert client.get(f"{base}/contact-sheet").status_code == 400
    assert client.post(f"{base}/concepts/generate", json={"batch": "C"}).status_code == 422
    batch(client, base, "B")
    concept = client.get(f"{base}/concepts").json()[0]
    other = client.post('/api/projects', json={"name": "Other project"}).json()["id"]
    assert client.post(f"/api/projects/{other}/concepts/{concept['id']}/enhance", json={}).status_code == 404
    assert client.post(f"/api/projects/{other}/concepts/{concept['id']}/regenerate", json={}).status_code == 404
    assert client.get(f"{base}/contact-sheet?run=999").status_code == 400
    assert client.get('/api/assets/missing/download').status_code == 404
    assert client.get('/api/projects/missing/export').status_code == 404
    assert client.delete(base).status_code == 204
    assert client.get(f"{base}/concepts").status_code == 404
