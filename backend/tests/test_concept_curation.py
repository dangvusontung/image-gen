import json

from app import concept_defaults
from app.concept_defaults import ACTIVE_DEFAULT_CONCEPTS, DEFAULT_CONCEPTS, RETIRED_CONCEPT_SLOTS
from tests.conftest import wait_for_job


def test_picker_reloads_edited_catalog_without_restarting(client, project, tmp_path, monkeypatch):
    path = tmp_path / 'concepts.json'
    catalog = json.loads(concept_defaults.CATALOG_PATH.read_text(encoding='utf-8'))
    path.write_text(json.dumps(catalog), encoding='utf-8')
    monkeypatch.setattr(concept_defaults, 'CATALOG_PATH', path)
    url = f'/api/projects/{project}/concept-proposals'
    assert client.get(url).json()[0]['title'] == catalog['concepts'][0]['title']
    catalog['concepts'][0]['title'] = 'Updated while the server is running'
    path.write_text(json.dumps(catalog), encoding='utf-8')
    assert client.get(url).json()[0]['title'] == 'Updated while the server is running'


def test_curated_picker_keeps_stable_slots_and_archive(client, project):
    base = f'/api/projects/{project}'
    visible = client.get(f'{base}/concept-proposals').json()
    archive = client.get(f'{base}/concept-proposals?include_retired=true').json()
    assert len(visible) == 141
    assert len(archive) == 157
    assert [p['slot'] for p in visible] == [slot for slot, _ in ACTIVE_DEFAULT_CONCEPTS]
    assert not set(RETIRED_CONCEPT_SLOTS) & {p['slot'] for p in visible}
    assert set(RETIRED_CONCEPT_SLOTS.values()) <= {p['slot'] for p in visible}
    assert [p['slot'] for p in visible[-5:]] == [153, 154, 155, 156, 157]
    for p in visible:
        assert p['id'] == f"default-{p['slot']}"
        assert p['title'] == DEFAULT_CONCEPTS[p['slot'] - 1]['title']


def test_bulk_defaults_skip_retired_but_historical_reruns_work(client, project, reference_ids):
    base = f'/api/projects/{project}'
    result = client.post(f'{base}/master/generate', json={}).json()
    assert wait_for_job(client, result['job_ids'][0])['status'] == 'succeeded'
    master = client.get(f'{base}/workflow').json()['masters'][0]
    assert client.post(f"{base}/master/{master['id']}/approve").status_code == 200
    # An explicit historical selection remains valid for previously saved work.
    old = client.post(f'{base}/concepts/generate', json={'slots': [48], 'confirmed': True})
    assert old.status_code == 201
    assert wait_for_job(client, old.json()['job_ids'][0])['status'] == 'succeeded'
    result = client.post(f'{base}/concepts/generate', json={'confirmed': True})
    assert result.status_code == 201, result.text
    assert len(result.json()['job_ids']) == 141
    concepts = client.get(f'{base}/concepts').json()
    new_ids = set(result.json()['concept_ids'])
    assert {c['slot'] for c in concepts if c['id'] in new_ids} == {s for s, _ in ACTIVE_DEFAULT_CONCEPTS}
    assert any(c['slot'] == 48 for c in concepts)


def test_rerun_selected_slots_creates_new_batch_with_saved_or_current_brief(client, project, reference_ids):
    base = f'/api/projects/{project}'
    result = client.post(f'{base}/master/generate', json={}).json()
    assert wait_for_job(client, result['job_ids'][0])['status'] == 'succeeded'
    master = client.get(f'{base}/workflow').json()['masters'][0]
    assert client.post(f"{base}/master/{master['id']}/approve").status_code == 200
    url = f'{base}/concepts/generate'
    original = client.post(url, json={'slots': [149, 152], 'briefs': {'152': {'pose': 'A saved pose from the source run'}}})
    assert original.status_code == 201
    assert client.post(url, json={'source_run': 1, 'slots': []}).status_code == 400
    assert client.post(url, json={'source_run': 1, 'slots': [151]}).status_code == 400
    for new_run, use_catalog, pose in [
        (2, False, 'A saved pose from the source run'),
        (3, True, DEFAULT_CONCEPTS[151]['pose']),
    ]:
        response = client.post(url, json={
            'source_run': 1,
            'slots': [152],
            'use_catalog_briefs': use_catalog,
            'choices': {'outfit': 'bikini', 'footwear': 'barefoot'},
        })
        assert response.status_code == 201, response.text
        rows = [c for c in client.get(f'{base}/concepts').json() if c['run'] == new_run]
        assert [c['slot'] for c in rows] == [152]
        assert rows[0]['brief']['pose'] == pose
        assert 'bikini' in rows[0]['brief']['outfit']
        assert 'bare feet' in rows[0]['brief']['footwear']


def test_single_concept_rerun_can_keep_saved_prompt_or_use_current_catalog(client, project, reference_ids):
    base = f'/api/projects/{project}'
    master_job = client.post(f'{base}/master/generate', json={}).json()['job_ids'][0]
    assert wait_for_job(client, master_job)['status'] == 'succeeded'
    master = client.get(f'{base}/workflow').json()['masters'][0]
    assert client.post(f"{base}/master/{master['id']}/approve").status_code == 200

    created = client.post(f'{base}/concepts/generate', json={
        'slots': [157], 'briefs': {'157': {'footwear': 'white ribbed leg warmers'}},
    }).json()
    url = f"{base}/concepts/{created['concept_ids'][0]}/regenerate"
    initial = wait_for_job(client, created['job_ids'][0])
    edited = client.post(url, json={'prompt': 'A saved custom prompt with white leg warmers.'}).json()
    old_url = f"{base}/concepts/{edited['concept_ids'][0]}/regenerate"

    saved = client.post(old_url, json={'prompt_mode': 'saved'})
    assert saved.status_code == 201
    saved_job = wait_for_job(client, saved.json()['job_ids'][0])
    assert saved_job['prompt'] == 'A saved custom prompt with white leg warmers.'
    assert saved_job['meta']['brief']['footwear'] == initial['meta']['brief']['footwear']

    current = client.post(old_url, json={'prompt_mode': 'current'})
    assert current.status_code == 201
    current_job = wait_for_job(client, current.json()['job_ids'][0])
    assert 'A saved custom prompt' not in current_job['prompt']
    assert current_job['meta']['brief']['footwear'] == DEFAULT_CONCEPTS[156]['footwear']
    assert 'uncovered ankles and calves' in current_job['prompt']
