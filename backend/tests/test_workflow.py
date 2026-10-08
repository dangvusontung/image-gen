from app.database import SessionLocal
from app.models import GenerationJob
from tests.conftest import wait_for_job


def generate_master(client, project):
    response = client.post(f"/api/projects/{project}/master/generate", json={"variants": 2})
    assert response.status_code == 201, response.text
    for job_id in response.json()["job_ids"]:
        assert wait_for_job(client, job_id)["status"] == "succeeded"
    return client.get(f"/api/projects/{project}/workflow").json()["masters"]


def test_full_workflow_preserves_versions(client, project, reference_ids):
    base = f"/api/projects/{project}"
    masters = generate_master(client, project)
    assert len(masters) == 2
    assert masters[0]["job"]["reference_asset_ids"] == reference_ids
    assert client.post(f"{base}/master/{masters[0]['id']}/approve").status_code == 200
    result = client.post(f"{base}/turnaround/generate", json={})
    assert result.status_code == 201, result.text
    turn = result.json()
    assert len(turn["job_ids"]) == 6
    for job_id in turn["job_ids"]:
        job = wait_for_job(client, job_id)
        assert job["status"] == "succeeded"
        assert job["reference_asset_ids"] == masters[0]["job"]["output_asset_ids"]
        assert job["meta"]["reference_labels"] == ["MASTER identity authority"]
    assert client.post(f"{base}/turnaround/{turn['id']}/approve").status_code == 200
    regen = client.post(f"{base}/turnaround/{turn['id']}/views/left90/regenerate")
    assert regen.status_code == 201, regen.text
    assert len(regen.json()["job_ids"]) == 1
    assert wait_for_job(client, regen.json()["job_ids"][0])["status"] == "succeeded"
    state = client.get(f"{base}/workflow").json()
    assert state["approved_turnaround_id"] == turn["id"]
    old, new = state["turnarounds"][1], state["turnarounds"][0]
    old_jobs = {v["angle"]: v["job"]["id"] for v in old["views"]}
    new_jobs = {v["angle"]: v["job"]["id"] for v in new["views"]}
    assert [k for k in old_jobs if old_jobs[k] != new_jobs[k]] == ["left90"]
    assert client.post(f"{base}/master/{masters[1]['id']}/approve").status_code == 200
    state = client.get(f"{base}/workflow").json()
    assert state["approved_turnaround_id"] is None
    assert all(t["stale"] for t in state["turnarounds"])
    assert len(state["approvals"]) == 3
    assert client.post(f"{base}/turnaround/{turn['id']}/approve").status_code == 409
    assert client.delete(base).status_code == 204


def test_prerequisites_and_project_isolation(client, project, reference_ids):
    base = f"/api/projects/{project}"
    assert client.post(f"{base}/turnaround/generate", json={}).status_code == 409
    other = client.post('/api/projects', json={"name": "Other"}).json()["id"]
    assert client.post(f"/api/projects/{other}/master/generate", json={}).status_code == 400
    masters = generate_master(client, project)
    assert client.post(f"/api/projects/{other}/master/{masters[0]['id']}/approve").status_code == 404
    client.patch(base, json={"rights_confirmed": False})
    assert client.post(f"{base}/master/generate", json={}).status_code == 403


def test_prompt_snapshot_and_reset(client, project, reference_ids):
    path = f"/api/prompts/master?project_id={project}"
    original = client.get(path).json()["body"]
    assert client.put(path, json={"body": "Invalid {unknown}"}).status_code == 400
    assert client.put(path, json={"body": "Custom master identity prompt"}).status_code == 200
    masters = generate_master(client, project)
    assert all(m["job"]["prompt"] == "Custom master identity prompt" for m in masters)
    assert client.put(path, json={"body": None}).json()["body"] == original
    assert client.get(f"/api/projects/{project}/workflow").json()["masters"][0]["job"]["prompt"] == "Custom master identity prompt"


def test_failed_angle_does_not_block_other_results(client, project, reference_ids):
    base = f"/api/projects/{project}"
    master = generate_master(client, project)[0]
    client.post(f"{base}/master/{master['id']}/approve")
    result = client.post(f"{base}/turnaround/generate", json={}).json()
    for job_id in result["job_ids"]:
        wait_for_job(client, job_id)
    with SessionLocal() as db:
        job = db.get(GenerationJob, result["job_ids"][0])
        job.status = "failed"
        job.output_asset_ids = []
        db.commit()
    assert client.post(f"{base}/turnaround/{result['id']}/approve").status_code == 409
    state = client.get(f"{base}/workflow").json()
    assert sum(v["job"]["status"] == "succeeded" for v in state["turnarounds"][0]["views"]) == 5
