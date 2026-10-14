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


def propose(client, base):
    response = client.post(f"{base}/concept-proposals")
    assert response.status_code == 201, response.text
    proposals = response.json()
    assert len(proposals) == 9
    return proposals


def render(client, base, proposals=None, **body):
    """Propose if needed, then render the given proposals (all of them by default)."""
    payload = {"confirmed": True, **body}
    if proposals is not None:
        payload["proposal_ids"] = [p["id"] for p in proposals]
    response = client.post(f"{base}/concepts/generate", json=payload)
    assert response.status_code == 201, response.text
    for job_id in response.json()["job_ids"]:
        wait_for_job(client, job_id)
    return response.json()


def test_nine_standalone_concepts_enhance_export_and_restart(client, studio):
    base, master, turn = studio
    proposals = propose(client, base)
    assert [p["slot"] for p in proposals] == list(range(1, 10))
    assert all(p["title"] and p["brief"]["setting"] for p in proposals)
    # Proposing alone renders nothing.
    assert client.get(f"{base}/concepts").json() == []
    rendered = render(client, base)
    assert len(rendered["job_ids"]) == 9
    concepts = client.get(f"{base}/concepts").json()
    assert len(concepts) == 9
    assert {c["slot"] for c in concepts} == set(range(1, 10))
    assert len({c["brief"]["setting"] for c in concepts}) == 9
    assert len({c["job"]["output_asset_ids"][0] for c in concepts}) == 9
    for c in concepts:
        assert c["job"]["status"] == "succeeded"
        assert set(c["brief"]) == {"setting", "activity", "outfit", "silhouette", "framing", "pose", "expression", "gaze", "camera", "lighting"}
        assert c["mood"] == next(p["title"] for p in proposals if p["slot"] == c["slot"])
        assert c["master_version_id"] == master["id"]
        assert c["turnaround_version_id"] == turn["id"]
        # Master and one randomly chosen turnaround angle; no style template.
        assert len(c["job"]["reference_asset_ids"]) == 2
        assert sum("TURNAROUND" in label for label in c["job"]["meta"]["reference_labels"]) == 1
    c = concepts[0]
    plan = client.get(f"{base}/concepts/{c['id']}/enhance-plan").json()
    assert not plan["warning"]
    # Enhancing edits one picture, so only that picture is sent.
    assert plan["reference_asset_ids"] == [c["job"]["output_asset_ids"][0]]
    assert plan["reference_labels"] == ["SELECTED CONCEPT scene and composition authority"]
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
    sheet = client.get(f"{base}/contact-sheet")
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
            if "Mood: Mock concept 2" in request.prompt and not self.failed_once:
                self.failed_once = True
                raise ProviderError("test_slot_failure", "One failed slot")
            return await super().submit(request)

    app.state.registry._providers["mock"] = FailOne(delay_seconds=0)
    proposals = propose(client, base)
    render(client, base, proposals[:5])
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
    # Regenerating re-renders the same brief, so the retry is a second attempt at one concept.
    newest = next(c for c in rows if c["revision"] == 3)
    assert newest["brief"] == failed["brief"]
    assert newest["job"]["output_asset_ids"] != failed["job"]["output_asset_ids"]


def test_reference_limit_never_silently_discards_and_enhance_sends_one_image(client, studio, monkeypatch):
    base, master, _ = studio
    propose(client, base)
    render(client, base)
    concept = client.get(f"{base}/concepts").json()[0]
    client.patch(base, json={"model": "mock-small-refs"})
    provider = app.state.registry.get("mock")
    models = provider.models()
    monkeypatch.setattr(provider, "models", lambda: [replace(model, max_reference_images=1) for model in models])
    before = len(client.get(f"{base}/jobs").json())
    response = client.post(f"{base}/concepts/generate", json={"confirmed": True})
    assert response.status_code == 400 and response.json()["detail"]["code"] == "reference_limit_exceeded"
    assert len(client.get(f"{base}/jobs").json()) == before
    # Enhancing edits one picture, so it fits even a two-reference model with nothing dropped
    # and no subset to confirm.
    path = f"{base}/concepts/{concept['id']}"
    plan = client.get(f"{path}/enhance-plan").json()
    assert plan["reference_asset_ids"] == [concept["job"]["output_asset_ids"][0]]
    assert plan["omitted_asset_ids"] == [] and plan["warning"] is None
    result = client.post(f"{path}/enhance", json={})
    assert result.status_code == 201
    job = wait_for_job(client, result.json()["job_ids"][0])
    assert job["status"] == "succeeded"
    assert job["reference_asset_ids"] == [concept["job"]["output_asset_ids"][0]]


def test_bulk_cost_confirmation_and_atomic_spend_guard(client, studio):
    base, _, _ = studio

    class PaidMock(MockProvider):
        name = "paid-test"

        def models(self):
            return [replace(super().models()[0], price_per_image_usd=0.1)]

    app.state.registry._providers["paid-test"] = PaidMock(delay_seconds=10)
    assert client.patch(base, json={"provider": "paid-test", "model": "mock-v1"}).status_code == 200
    before = len(client.get(f"{base}/jobs").json())
    proposals = propose(client, base)
    denied = client.post(f"{base}/concepts/generate", json={"proposal_ids": [p["id"] for p in proposals[:5]]})
    assert denied.status_code == 400 and denied.json()["detail"]["code"] == "bulk_confirmation_required"
    assert len(client.get(f"{base}/jobs").json()) == before
    assert client.get(f"{base}/concepts").json() == []
    ids = [p["id"] for p in proposals]
    assert client.post(f"{base}/concepts/generate", json={"proposal_ids": ids[:5], "confirmed": True}).status_code == 201
    assert client.post(f"{base}/concepts/generate", json={"proposal_ids": ids[5:], "confirmed": True}).status_code == 201
    # 0.5 + 0.4 fits the $1 cap. A further run must roll back every slot.
    rejected = client.post(f"{base}/concepts/generate", json={"proposal_ids": ids[:5], "confirmed": True})
    assert rejected.status_code == 402, rejected.text
    assert len(client.get(f"{base}/concepts").json()) == 9


def test_rerendering_reuses_each_proposal_and_a_new_master_marks_stale(client, studio):
    base, _, _ = studio
    proposals = propose(client, base)
    render(client, base)
    render(client, base)
    rows = client.get(f"{base}/concepts").json()
    assert {c["run"] for c in rows} == {1, 2}
    # Both runs render the same nine briefs, so the two attempts stay comparable slot by slot.
    by_slot = {p["slot"]: p["brief"] for p in proposals}
    for c in rows:
        assert c["brief"] == by_slot[c["slot"]]
    # A fresh proposal round invents new briefs rather than reusing the old ones.
    again = propose(client, base)
    assert [p["slot"] for p in again] == list(range(1, 10))
    assert {p["id"] for p in again}.isdisjoint({p["id"] for p in proposals})
    generated = client.post(f"{base}/master/generate", json={}).json()
    wait_for_job(client, generated["job_ids"][0])
    new_master = client.get(f"{base}/workflow").json()["masters"][0]
    client.post(f"{base}/master/{new_master['id']}/approve")
    assert all(c["stale"] for c in client.get(f"{base}/concepts").json())


def test_exports_validation_and_project_isolation(client, studio):
    base, _, _ = studio
    assert client.get(f"{base}/contact-sheet").status_code == 400
    # With no proposed round, the step offers the built-in nine straight from the prompt.
    built_in = client.get(f"{base}/concept-proposals").json()
    assert len(built_in) == 28 and all(p["run"] == 0 for p in built_in)
    propose(client, base)
    unknown = client.post(f"{base}/concepts/generate", json={"proposal_ids": ["nope"], "confirmed": True})
    assert unknown.status_code == 404 and unknown.json()["detail"]["code"] == "proposal_not_found"
    render(client, base)
    concept = client.get(f"{base}/concepts").json()[0]
    other = client.post('/api/projects', json={"name": "Other project"}).json()["id"]
    assert client.post(f"/api/projects/{other}/concepts/{concept['id']}/enhance", json={}).status_code == 404
    assert client.post(f"/api/projects/{other}/concepts/{concept['id']}/regenerate", json={}).status_code == 404
    assert client.get(f"{base}/contact-sheet?run=999").status_code == 400
    assert client.get('/api/assets/missing/download').status_code == 404
    assert client.get('/api/projects/missing/export').status_code == 404
    assert client.delete(base).status_code == 204
    assert client.get(f"{base}/concepts").status_code == 404


def test_concepts_can_exclude_an_approved_turnaround(client, studio):
    base, master, _ = studio
    response = client.put(f"{base}/step-lead", json={"step": "concept", "lead": "none"})
    assert response.status_code == 200
    proposals = propose(client, base)
    rendered = render(client, base, proposals[:1])
    job = wait_for_job(client, rendered["job_ids"][0])
    assert job["status"] == "succeeded"
    assert job["reference_asset_ids"] == [master["job"]["output_asset_ids"][0]]
    estimate = client.get(f"{base}/generation-estimate", params={"purpose": "concept", "count": 1})
    assert estimate.status_code == 200
    assert estimate.json()["reference_count"] == 1
    assert client.get(base).json()["step_leads"]["concept"] == "none"


def test_default_concepts_mix_direct_and_slightly_off_camera_gaze():
    from app.concept_defaults import DEFAULT_CONCEPTS
    from app.routes.concepts import preferred_angle
    assert len(DEFAULT_CONCEPTS) == 28
    direct = [c for c in DEFAULT_CONCEPTS[:9] if c["gaze"] == "looking directly into the camera lens, eyes open"]
    assert len(direct) == 5
    off_camera = [c for c in DEFAULT_CONCEPTS[:9] if c not in direct]
    assert len(off_camera) == 4
    for concept in off_camera:
        assert "degrees" in concept["gaze"] and "both eyes visible" in concept["pose"]
    for concept in DEFAULT_CONCEPTS[:9]:
        assert concept["camera"].startswith("straight-on frontal view at eye level")
        assert preferred_angle(concept["camera"]) == "front"
        assert "eyes closed" not in concept["expression"]
        assert "side profile" not in concept["pose"]


def test_regenerate_uses_exact_edited_prompt_and_keeps_it_for_next_revision(client, studio):
    base, _, _ = studio
    proposals = propose(client, base)
    result = render(client, base, proposals[:1])
    wait_for_job(client, result['job_ids'][0])
    concept_id = result['concept_ids'][0]
    edited = 'Render this same character at the pool, wearing a blue shirt.'
    response = client.post(f'{base}/concepts/{concept_id}/regenerate', json={'prompt': edited})
    assert response.status_code == 201
    job = wait_for_job(client, response.json()['job_ids'][0])
    assert job['prompt'] == edited and job['meta']['prompt_edited']
    again = client.post(f"{base}/concepts/{response.json()['id']}/regenerate", json={})
    assert again.status_code == 201
    assert wait_for_job(client, again.json()['job_ids'][0])['prompt'] == edited
    assert client.get(f'{base}/concepts').json()[0]['revision'] == 3


def test_seven_added_concepts_are_selectable_and_renderable(client, studio):
    base, _, _ = studio
    defaults = client.get(f'{base}/concept-proposals').json()
    assert len(defaults) == 28
    added = defaults[9:16]
    assert [p['slot'] for p in added] == list(range(10, 17))
    assert [p['title'] for p in added] == ['At-home manicure', 'Soft morning knit', 'Kitchen daydream',
        'Golden window stretch', 'Window-seat crochet', 'Petal afternoon nap', 'Floral pillow rest']
    for concept in added:
        assert set(concept['brief']) == set(defaults[0]['brief'])
        assert all(concept['brief'].values())
    assert client.get(f'{base}/generation-estimate', params={'purpose': 'concept', 'count': 16}).status_code == 200
    result = client.post(f'{base}/concepts/generate', json={'slots': list(range(10, 17)), 'confirmed': True})
    assert result.status_code == 201, result.text
    assert len(result.json()['job_ids']) == 7
    for job_id in result.json()['job_ids']:
        assert wait_for_job(client, job_id)['status'] == 'succeeded'
    assert {c['slot'] for c in client.get(f'{base}/concepts').json()} == set(range(10, 17))


def test_latest_reference_scenes_generate_only_selected_slots(client, studio):
    base, _, _ = studio
    defaults = client.get(f'{base}/concept-proposals').json()
    assert [p['slot'] for p in defaults[16:23]] == list(range(17, 24))
    assert client.get(f'{base}/generation-estimate', params={'purpose': 'concept', 'count': 23}).status_code == 200
    response = client.post(f'{base}/concepts/generate', json={'slots': [17, 23], 'confirmed': True})
    assert response.status_code == 201, response.text
    assert len(response.json()['job_ids']) == 2
    for job_id in response.json()['job_ids']:
        job = wait_for_job(client, job_id)
        assert job['status'] == 'succeeded'
        assert 'bikini' not in job['prompt']
    assert {c['slot'] for c in client.get(f'{base}/concepts').json()} == {17, 23}


def test_clothed_reference_concepts_keep_their_own_outfits(client, studio):
    base, _, _ = studio
    defaults = client.get(f'{base}/concept-proposals').json()
    added = defaults[23:26]
    assert [p['slot'] for p in added] == [24, 25, 26]
    for concept, clothing in zip(added, ['long dress', 'corduroy trousers', 'slip dress'], strict=True):
        assert clothing in concept['brief']['outfit']
        assert 'bikini' not in concept['brief']['outfit']
    result = client.post(f'{base}/concepts/generate', json={'slots': [24, 25, 26], 'confirmed': True})
    assert result.status_code == 201, result.text
    for job_id in result.json()['job_ids']:
        job = wait_for_job(client, job_id)
        assert job['status'] == 'succeeded'
        assert 'bikini' not in job['prompt']


def test_optional_glasses_are_added_to_prompt_without_replacing_outfit(client, studio):
    base, _, _ = studio
    defaults = client.get(f'{base}/concept-proposals').json()
    assert [p['slot'] for p in defaults[26:]] == [27, 28]
    for slot, choices in [(27, {'glasses': True}), (28, {})]:
        result = client.post(f'{base}/concepts/generate', json={'slots': [slot], 'choices': choices, 'confirmed': True})
        assert result.status_code == 201, result.text
        job = wait_for_job(client, result.json()['job_ids'][0])
        assert job['status'] == 'succeeded'
        assert ('clear-lens eyeglasses' in job['prompt']) == (slot == 27)
        assert 'jeans' in job['prompt']
