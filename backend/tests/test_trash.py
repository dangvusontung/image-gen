from app.database import SessionLocal
from app.models import Asset, GenerationJob
from app.routes.assets import storage
from .conftest import wait_for_job


def test_run_trash_restore_and_purge_preserve_accounting(client, project, enqueue):
    job_id = enqueue()
    job = wait_for_job(client, job_id)
    asset_id = job['output_asset_ids'][0]
    with SessionLocal() as db:
        db.get(GenerationJob, job_id).actual_cost_usd = .25
        db.commit()
    assert client.delete(f'/api/jobs/{job_id}').status_code == 200
    assert client.get('/api/gallery').json()['total'] == 0
    assert client.get('/api/jobs').json() == []
    trash = client.get('/api/trash').json()
    assert trash[0]['id'] == job_id
    assert trash[0]['asset_ids'] == [asset_id]
    assert client.get(f'/api/assets/{asset_id}/content').status_code == 200
    assert client.post(f'/api/trash/job/{job_id}/restore').status_code == 200
    assert client.get('/api/gallery').json()['total'] == 1
    assert client.get('/api/trash').json() == []
    assert client.delete(f'/api/trash/job/{job_id}').status_code == 409
    client.delete(f'/api/jobs/{job_id}')
    assert client.delete(f'/api/trash/job/{job_id}').status_code == 200
    assert client.get('/api/trash').json() == []
    assert client.get(f'/api/assets/{asset_id}/content').status_code == 404
    assert client.post(f'/api/trash/job/{job_id}/restore').status_code in (404, 409)
    with SessionLocal() as db:
        kept = db.get(GenerationJob, job_id)
        assert kept.purged and kept.dismissed and kept.actual_cost_usd == .25


def test_individual_image_trash_survives_run_restore(client, project, enqueue):
    job_id = enqueue()
    job = wait_for_job(client, job_id)
    asset_id = job['output_asset_ids'][0]
    assert client.post(f'/api/trash/assets/{asset_id}').status_code == 200
    assert client.get('/api/gallery').json()['total'] == 0
    assert client.get(f'/api/jobs/{job_id}').json()['output_asset_ids'] == []
    assert client.get('/api/trash').json()[0]['kind'] == 'asset'
    client.delete(f'/api/jobs/{job_id}')
    assert [r['kind'] for r in client.get('/api/trash').json()] == ['job']
    client.post(f'/api/trash/job/{job_id}/restore')
    assert client.get('/api/trash').json()[0]['kind'] == 'asset'
    assert client.post(f'/api/trash/asset/{asset_id}/restore').status_code == 200
    assert client.get('/api/gallery').json()['total'] == 1
    assert client.get(f'/api/jobs/{job_id}').json()['output_asset_ids'] == [asset_id]
    assert client.delete(f'/api/trash/asset/{asset_id}').status_code == 409
    client.post(f'/api/trash/assets/{asset_id}')
    with SessionLocal() as db:
        path = db.get(Asset, asset_id).file_path
    assert client.delete(f'/api/trash/asset/{asset_id}').status_code == 200
    assert client.get('/api/trash').json() == []
    assert not (storage.base_path / path).exists()
    assert client.get(f'/api/jobs/{job_id}').json()['output_asset_ids'] == []


def test_purge_rejects_reference_and_source(client, project, reference_ids, enqueue):
    assert client.post(f'/api/trash/assets/{reference_ids[0]}').status_code == 409
    job_id = enqueue()
    job = wait_for_job(client, job_id)
    asset_id = job['output_asset_ids'][0]
    other = enqueue(reference_asset_ids=[asset_id])
    wait_for_job(client, other)
    client.delete(f'/api/jobs/{job_id}')
    assert client.delete(f'/api/trash/job/{job_id}').status_code == 409
    assert client.get(f'/api/assets/{asset_id}/content').status_code == 200


def test_active_job_cannot_be_trashed(client, project):
    with SessionLocal() as db:
        job = GenerationJob(project_id=project, purpose='test', provider='mock', model='mock-v1', prompt='x', status='running')
        db.add(job)
        db.commit()
        job_id = job.id
    assert client.delete(f'/api/jobs/{job_id}').status_code == 409
    assert client.get('/api/trash').json() == []
