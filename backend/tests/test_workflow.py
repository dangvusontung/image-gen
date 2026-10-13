from app.database import SessionLocal
from app.routes.workflow import TEMPLATE_LABEL
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
    # Only identity photos are sent; no style-template reference.
    assert masters[0]["job"]["reference_asset_ids"] == reference_ids
    assert client.post(f"{base}/master/{masters[0]['id']}/approve").status_code == 200
    result = client.post(f"{base}/turnaround/generate", json={})
    assert result.status_code == 201, result.text
    turn = result.json()
    assert len(turn["job_ids"]) == 6
    for job_id in turn["job_ids"]:
        job = wait_for_job(client, job_id)
        assert job["status"] == "succeeded"
        assert job["reference_asset_ids"] == [*masters[0]["job"]["output_asset_ids"], *reference_ids]
        assert job["meta"]["reference_labels"] == ["MASTER identity authority", *["Real reference photo, identity guidance"] * len(reference_ids)]
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
    assert all(m["job"]["prompt"].startswith("Custom master identity prompt") for m in masters)
    assert client.put(path, json={"body": None}).json()["body"] == original
    assert client.get(f"/api/projects/{project}/workflow").json()["masters"][0]["job"]["prompt"].startswith("Custom master identity prompt")


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


def test_every_registered_template_has_a_loadable_file():
    # A typo in a spec's name or version would otherwise only surface at generation time.
    from app.prompts import SPECS, default_body, validate_body
    for name, spec in SPECS.items():
        assert spec.path.exists(), f"missing template file for {name}"
        validate_body(name, default_body(name))


def test_provider_template_prefers_a_registered_variant():
    from app.prompts import provider_template
    assert provider_template("master", "bfl") == "master_flux"
    assert provider_template("master", "gemini") == "master"
    assert provider_template("master", "mock") == "master"
    # No variant is registered for these, so the base template stands.
    assert provider_template("concept", "bfl") == "concept"
    assert provider_template("enhance", "bfl") == "enhance"


def test_flux_projects_render_the_master_from_the_flux_prompt(client, project, reference_ids):
    from dataclasses import replace

    from app.main import app
    from app.providers.mock import MockProvider

    class FakeFlux(MockProvider):
        name = "bfl"

        def models(self):
            return [replace(super().models()[0], id="flux-2-pro", display_name="FLUX.2 [pro]")]

    base = f"/api/projects/{project}"
    original = app.state.registry._providers.get("bfl")
    app.state.registry._providers["bfl"] = FakeFlux(delay_seconds=0)
    try:
        assert client.patch(base, json={"provider": "bfl", "model": "flux-2-pro"}).status_code == 200
        flux = client.post(f"{base}/master/generate", json={}).json()["job_ids"][0]
        assert wait_for_job(client, flux)["status"] == "succeeded"
        job = client.get(f"/api/jobs/{flux}").json()
        assert job["meta"]["template_name"] == "master_flux"
        assert "PRIMARY GOAL — FACIAL LIKENESS" in job["prompt"]

        # Switching back to a provider without a variant restores the base prompt.
        assert client.patch(base, json={"provider": "mock", "model": "mock-v1"}).status_code == 200
        plain = client.post(f"{base}/master/generate", json={}).json()["job_ids"][0]
        assert wait_for_job(client, plain)["status"] == "succeeded"
        plain_job = client.get(f"/api/jobs/{plain}").json()
        assert plain_job["meta"]["template_name"] == "master"
        assert "IDENTITY — HIGHEST PRIORITY" in plain_job["prompt"]
    finally:
        if original is not None:
            app.state.registry._providers["bfl"] = original


def test_turnaround_uses_selected_reference_photos_and_estimates_same_inputs(client, project, reference_ids):
    base = f"/api/projects/{project}"
    masters = generate_master(client, project)
    client.post(f"{base}/master/{masters[0]['id']}/approve")
    client.patch(f"/api/assets/{reference_ids[0]}", json={"selected": False})
    estimate = client.get(f"{base}/generation-estimate", params={"purpose": "turnaround", "count": 1})
    assert estimate.json()["reference_count"] == len(reference_ids)
    result = client.post(f"{base}/turnaround/generate", json={"angles": ["left90"]})
    assert result.status_code == 201
    job = wait_for_job(client, result.json()["job_ids"][0])
    assert job["status"] == "succeeded"
    assert job["reference_asset_ids"] == [*masters[0]["job"]["output_asset_ids"], *reference_ids[1:]]


def test_copy_configuration_includes_models_and_prompts_without_copying_assets(client, project, reference_ids):
    source = client.post('/api/projects', json={'name': 'Source configuration'}).json()['id']
    assert client.patch(f'/api/projects/{source}', json={'provider': 'mock', 'model': 'mock-small-refs'}).status_code == 200
    original = client.get(f'/api/prompts/master?project_id={source}').json()['body']
    body = 'Source-specific direction.\n' + original
    assert client.put(f'/api/prompts/master?project_id={source}', json={'body': body}).status_code == 200
    preview = client.get(f'/api/projects/{source}/configuration').json()
    assert preview['model'] == 'mock-small-refs'
    assert preview['prompts']['master'] == body
    response = client.post(f'/api/projects/{project}/prompts/copy', json={
        'source_project_id': source, 'include_configuration': True})
    assert response.status_code == 200
    target = client.get(f'/api/projects/{project}').json()
    assert target['model'] == 'mock-small-refs'
    assert target['rights_confirmed'] is True
    assert {asset['id'] for asset in target['assets']} == set(reference_ids)
    assert client.get(f'/api/prompts/master?project_id={project}').json()['body'] == body
    assert client.get(f'/api/projects/{project}/jobs').json() == []


def test_copy_one_prompt_leaves_other_prompts_and_model_unchanged(client, project):
    source = client.post('/api/projects', json={'name': 'Single prompt source'}).json()['id']
    previous_master = client.get(f'/api/prompts/master?project_id={project}').json()['body']
    previous_concept = client.get(f'/api/prompts/concept?project_id={project}').json()['body']
    source_concept = 'Source concept instructions.\n' + previous_concept
    source_master = 'Source master instructions.\n' + previous_master
    client.put(f'/api/prompts/concept?project_id={source}', json={'body': source_concept})
    client.put(f'/api/prompts/master?project_id={source}', json={'body': source_master})
    client.patch(f'/api/projects/{source}', json={'model': 'mock-small-refs'})
    response = client.post(f'/api/projects/{project}/prompts/copy', json={'source_project_id': source, 'prompt_names': ['concept']})
    assert response.status_code == 200
    assert len(response.json()) == 1
    assert client.get(f'/api/prompts/concept?project_id={project}').json()['body'] == source_concept
    assert client.get(f'/api/prompts/master?project_id={project}').json()['body'] == previous_master
    assert client.get(f'/api/projects/{project}').json()['model'] == 'mock-v1'
