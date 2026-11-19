import io

from tests.conftest import make_image, wait_for_job


def test_master_outfit_uses_selected_reference_without_duplicating_inputs(client, project, reference_ids):
    base = f"/api/projects/{project}"
    response = client.put(f"{base}/step-lead", json={"step": "master", "lead": reference_ids[2]})
    assert response.status_code == 200, response.text
    response = client.post(f"{base}/master/generate", json={
        "variants": 2, "confirmed": True, "outfit_reference_asset_id": reference_ids[0], "hairstyle": "bob",
    })
    assert response.status_code == 201, response.text
    for job_id in response.json()["job_ids"]:
        job = wait_for_job(client, job_id)
        assert job["status"] == "succeeded"
        assert job["reference_asset_ids"] == [reference_ids[2], reference_ids[0], reference_ids[1]]
        assert job["meta"]["outfit_reference_asset_id"] == reference_ids[0]
        assert job["meta"]["outfit_reference_index"] == 2
        assert job["meta"]["reference_labels"][1] == "OUTFIT SOURCE, clothing only"
        assert "MASTER OUTFIT — PRIORITY OVERRIDE" in job["prompt"]
        assert "Reference image 2" in job["prompt"]
        assert "hairstyle" in job["prompt"]
        assert job["meta"]["hairstyle"]["style"] == "bob"


def test_invalid_outfit_sources_queue_no_jobs(client, project, reference_ids):
    base = f"/api/projects/{project}"
    other = client.post('/api/projects', json={"name": "Other"}).json()["id"]
    client.patch(f"/api/projects/{other}", json={"rights_confirmed": True})
    upload = client.post(f"/api/projects/{other}/assets", files=[("files", ("other.png", io.BytesIO(make_image()), "image/png"))])
    other_id = upload.json()[0]["id"]
    assert client.patch(f"/api/assets/{reference_ids[1]}", json={"selected": False}).status_code == 200
    from app.database import SessionLocal
    from app.models import Asset
    with SessionLocal() as db:
        db.get(Asset, reference_ids[2]).trashed = True
        db.commit()
    for asset_id in ("missing", other_id, reference_ids[1], reference_ids[2]):
        response = client.post(f"{base}/master/generate", json={"outfit_reference_asset_id": asset_id})
        assert response.status_code == 400, response.text
        assert response.json()["detail"]["code"] == "outfit_reference_invalid"
    assert client.get(f"{base}/workflow").json()["masters"] == []


def test_single_reference_can_supply_both_identity_and_outfit(client, project, reference_ids):
    for id in reference_ids[1:]:
        client.patch(f"/api/assets/{id}", json={"selected": False})
    response = client.post(f"/api/projects/{project}/master/generate", json={"outfit_reference_asset_id": reference_ids[0]})
    assert response.status_code == 201, response.text
    job = wait_for_job(client, response.json()["job_ids"][0])
    assert job["reference_asset_ids"] == reference_ids[:1]
    assert job["meta"]["reference_labels"] == ["IDENTITY + OUTFIT SOURCE"]
    assert "single reference supplies identity and clothing" in job["prompt"]


def test_default_master_keeps_existing_prompt_behavior(client, project, reference_ids):
    response = client.post(f"/api/projects/{project}/master/generate", json={})
    job = wait_for_job(client, response.json()["job_ids"][0])
    assert job["reference_asset_ids"] == reference_ids
    assert "outfit_reference_asset_id" not in job["meta"]
    assert "MASTER OUTFIT — PRIORITY OVERRIDE" not in job["prompt"]


def test_template_outfit_is_appended_without_using_its_identity(client, project, reference_ids):
    response = client.post(f'/api/projects/{project}/assets', data={'kind': 'template'}, files=[('files', ('outfit.png', make_image(), 'image/png'))])
    template_id = response.json()[0]['id']
    response = client.post(f'/api/projects/{project}/master/generate', json={'outfit_reference_asset_id': template_id})
    assert response.status_code == 201, response.text
    job = wait_for_job(client, response.json()['job_ids'][0])
    assert job['reference_asset_ids'] == reference_ids + [template_id]
    assert job['meta']['reference_labels'][-1] == 'OUTFIT SOURCE, clothing only'
    assert job['meta']['outfit_reference_index'] == 4


def test_master_presets_reuse_catalog_and_reject_mixed_sources(client, project, reference_ids):
    base = f'/api/projects/{project}'
    options = client.get(f'{base}/master/outfit-options').json()['outfit']
    assert ['black_strapless_mini', 'Váy mini đen cúp ngực'] in options
    assert not any(key in ('auto', 'master') for key, _ in options)
    response = client.post(f'{base}/master/generate', json={'master_outfit': {'outfit': 'black_strapless_mini'}})
    assert response.status_code == 201, response.text
    job = wait_for_job(client, response.json()['job_ids'][0])
    assert job['reference_asset_ids'] == reference_ids
    assert job['meta']['outfit']['mode'] == 'preset'
    assert 'strapless' in job['meta']['outfit']['description']
    assert 'MASTER OUTFIT — PRIORITY OVERRIDE' in job['prompt']
    for extra in ({'outfit_reference_asset_id': reference_ids[0]},):
        assert client.post(f'{base}/master/generate', json={'master_outfit': {'outfit': 'bikini'}, **extra}).status_code == 422
    assert client.post(f'{base}/master/generate', json={'master_outfit': {'outfit': 'unknown'}}).status_code == 422
    assert client.post(f'{base}/master/generate', json={'master_outfit': {'outfit': 'bikini', 'scene': 'beach'}}).status_code == 422


def test_edit_completed_master_outfit_creates_version_without_autoapproval(client, project, reference_ids):
    base = f'/api/projects/{project}'
    created = client.post(f'{base}/master/generate', json={}).json()
    wait_for_job(client, created['job_ids'][0])
    original = client.get(f'{base}/workflow').json()['masters'][0]
    client.post(f"{base}/master/{original['id']}/approve")
    response = client.post(f"{base}/master/{original['id']}/outfit", json={'outfit_reference_asset_id': reference_ids[1]})
    assert response.status_code == 201, response.text
    job = wait_for_job(client, response.json()['job_ids'][0])
    assert job['reference_asset_ids'] == [original['job']['output_asset_ids'][0], reference_ids[1]]
    assert job['meta']['edit_type'] == 'master_outfit'
    assert job['meta']['source_master_version_id'] == original['id']
    assert 'Change ONLY its outfit' in job['prompt']
    workflow = client.get(f'{base}/workflow').json()
    assert len(workflow['masters']) == 2
    assert workflow['approved_master_id'] == original['id']
    edited = next(row for row in workflow['masters'] if row['id'] != original['id'])
    assert client.post(f"{base}/master/{edited['id']}/approve").status_code == 200
    other = client.post('/api/projects', json={'name': 'Other'}).json()['id']
    assert client.post(f"/api/projects/{other}/master/{original['id']}/outfit", json={'outfit_reference_asset_id': reference_ids[0]}).status_code == 404
    assert client.post(f"{base}/master/{original['id']}/outfit", json={'outfit_reference_asset_id': 'missing'}).status_code == 400
