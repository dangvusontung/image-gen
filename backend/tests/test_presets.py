"""Per-step presets decide the provider, model and size for every project that uses them."""
from tests.conftest import wait_for_job


def test_preset_crud_rejects_models_this_install_cannot_use(client):
    bad = client.post("/api/presets", json={"name": "Sai", "steps": {"master": {"provider": "nope", "model": "x"}}})
    assert bad.status_code == 400 and bad.json()["detail"]["code"] == "unknown_provider"

    bad_size = client.post("/api/presets", json={
        "name": "Sai size", "steps": {"master": {"provider": "mock", "model": "mock-v1", "size": "9K"}}})
    assert bad_size.status_code == 400 and bad_size.json()["detail"]["code"] == "unsupported_size"

    created = client.post("/api/presets", json={
        "name": "Chuẩn", "steps": {"master": {"provider": "mock", "model": "mock-v1"}}})
    assert created.status_code == 201, created.text
    preset = created.json()
    assert preset["steps"]["master"]["provider"] == "mock"

    renamed = client.put(f"/api/presets/{preset['id']}", json={
        "name": "Chuẩn 2", "steps": {"enhance": {"provider": "mock", "model": "mock-small-refs"}}})
    assert renamed.status_code == 200
    assert renamed.json()["name"] == "Chuẩn 2" and set(renamed.json()["steps"]) == {"enhance"}
    assert [p["id"] for p in client.get("/api/presets").json()] == [preset["id"]]
    assert client.put("/api/presets/nope", json={"name": "x", "steps": {}}).status_code == 404


def test_a_preset_routes_each_step_and_survives_being_deleted(client, project, reference_ids):
    base = f"/api/projects/{project}"
    preset = client.post("/api/presets", json={"name": "Theo bước", "steps": {
        "master": {"provider": "mock", "model": "mock-small-refs"},
    }}).json()

    assert client.patch(base, json={"preset_id": preset["id"]}).json()["preset_id"] == preset["id"]
    assert client.patch(base, json={"preset_id": "nope"}).status_code == 404

    # The preset overrides the project's own provider/model for the step it names.
    assert client.get(base).json()["model"] == "mock-v1"
    refused = client.post(f"{base}/master/generate", json={})
    assert refused.status_code == 400
    assert refused.json()["detail"]["code"] == "reference_limit_exceeded"  # mock-small-refs takes 2

    client.put(f"/api/presets/{preset['id']}", json={"name": "Theo bước", "steps": {
        "master": {"provider": "mock", "model": "mock-v1"},
    }})
    result = client.post(f"{base}/master/generate", json={})
    assert result.status_code == 201, result.text
    job = wait_for_job(client, result.json()["job_ids"][0])
    assert job["provider"] == "mock" and job["model"] == "mock-v1"

    # Deleting a preset must not strand the projects pointing at it.
    assert client.delete(f"/api/presets/{preset['id']}").status_code == 204
    assert client.get(base).json()["preset_id"] is None
    assert client.post(f"{base}/master/generate", json={}).status_code == 201
