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
