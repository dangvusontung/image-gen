import pytest

from tests.conftest import wait_for_job


@pytest.fixture()
def clone_master(client, project, reference_ids):
    base = f'/api/projects/{project}'
    result = client.post(f'{base}/master/generate', json={}).json()
    wait_for_job(client, result['job_ids'][0])
    master = client.get(f'{base}/workflow').json()['masters'][0]
    client.post(f"{base}/master/{master['id']}/approve")
    return base, master


@pytest.mark.parametrize('keep', [False, True])
def test_clone_uses_exactly_master_and_reference_and_creates_a_batch(client, clone_master, reference_ids, keep):
    base, master = clone_master
    response = client.post(f'{base}/concepts/clone', json={'reference_asset_id': reference_ids[0], 'keep_master_outfit': keep})
    assert response.status_code == 201, response.text
    job = wait_for_job(client, response.json()['job_ids'][0])
    assert job['reference_asset_ids'] == [master['job']['output_asset_ids'][0], reference_ids[0]]
    assert job['meta']['image_clone'] is True
    assert job['meta']['clone_keep_master_outfit'] is keep
    assert len(job['meta']['reference_labels']) == 2
    assert ('Keep the exact clothing' if keep else 'Copy the clothing') in job['prompt']
    concept = client.get(f'{base}/concepts').json()[0]
    assert concept['id'] == response.json()['concept_ids'][0]
    assert concept['run'] == 1
    assert concept['turnaround_version_id'] is None
    assert concept['master_version_id'] == master['id']
    assert not concept['bookmark_key'].startswith('default:')


def test_clone_retries_preserve_reference_and_outfit_choice(client, clone_master, reference_ids):
    base, master = clone_master
    response = client.post(f'{base}/concepts/clone', json={'reference_asset_id': reference_ids[0], 'keep_master_outfit': True})
    original_job = wait_for_job(client, response.json()['job_ids'][0])
    concept_id = response.json()['concept_ids'][0]
    for payload in ({'prompt_mode': 'saved'}, {'prompt_mode': 'current'}, {'prompt': 'Custom clone instruction'}):
        retried = client.post(f'{base}/concepts/{concept_id}/regenerate', json=payload)
        assert retried.status_code == 201, retried.text
        job = wait_for_job(client, retried.json()['job_ids'][0])
        assert job['reference_asset_ids'] == original_job['reference_asset_ids']
        assert job['meta']['clone_keep_master_outfit'] is True
        if payload.get('prompt_mode') == 'saved':
            assert job['prompt'] == original_job['prompt']
        if 'prompt' in payload:
            assert job['prompt'] == payload['prompt']
    original = next(row for row in client.get(f'{base}/concepts').json() if row['id'] == concept_id)
    rerun = client.post(f'{base}/concepts/generate', json={'source_run': original['run'], 'slots': [original['slot']]})
    assert rerun.status_code == 201, rerun.text
    job = wait_for_job(client, rerun.json()['job_ids'][0])
    assert job['meta']['image_clone'] is True
    assert job['reference_asset_ids'] == original_job['reference_asset_ids']


def test_clone_validates_sources_and_accepts_an_explicit_master(client, clone_master, reference_ids):
    base, master = clone_master
    other = client.post('/api/projects', json={'name': 'Other'}).json()['id']
    assert client.post(f'/api/projects/{other}/concepts/clone', json={'master_version_id': master['id'], 'reference_asset_id': reference_ids[0]}).status_code == 404
    assert client.post(f'{base}/concepts/clone', json={'reference_asset_id': 'missing'}).status_code == 400
    assert client.post(f'{base}/concepts/clone', json={'reference_asset_id': master['job']['output_asset_ids'][0]}).status_code == 422
    assert client.get(f'{base}/concepts').json() == []


def test_clone_respects_an_explicit_unapproved_master(client, clone_master, reference_ids):
    base, approved = clone_master
    result = client.post(f'{base}/master/generate', json={}).json()
    wait_for_job(client, result['job_ids'][0])
    chosen = next(row for row in client.get(f'{base}/workflow').json()['masters'] if row['id'] != approved['id'])
    response = client.post(f'{base}/concepts/clone', json={'master_version_id': chosen['id'], 'reference_asset_id': reference_ids[0]})
    assert response.status_code == 201, response.text
    job = wait_for_job(client, response.json()['job_ids'][0])
    assert job['reference_asset_ids'][0] == chosen['job']['output_asset_ids'][0]
    assert client.get(f'{base}/workflow').json()['approved_master_id'] == approved['id']
