from app.concept_defaults import ACTIVE_DEFAULT_CONCEPTS, DEFAULT_CONCEPTS, RETIRED_CONCEPT_SLOTS
from tests.conftest import wait_for_job


def test_curated_picker_keeps_stable_slots_and_archive(client, project):
    base = f'/api/projects/{project}'
    visible = client.get(f'{base}/concept-proposals').json()
    archive = client.get(f'{base}/concept-proposals?include_retired=true').json()
    assert len(visible) == 129
    assert len(archive) == 145
    assert [p['slot'] for p in visible] == [slot for slot, _ in ACTIVE_DEFAULT_CONCEPTS]
    assert not set(RETIRED_CONCEPT_SLOTS) & {p['slot'] for p in visible}
    assert set(RETIRED_CONCEPT_SLOTS.values()) <= {p['slot'] for p in visible}
    assert [p['slot'] for p in visible[-5:]] == [141, 142, 143, 144, 145]
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
    assert len(result.json()['job_ids']) == 129
    concepts = client.get(f'{base}/concepts').json()
    new_ids = set(result.json()['concept_ids'])
    assert {c['slot'] for c in concepts if c['id'] in new_ids} == {s for s, _ in ACTIVE_DEFAULT_CONCEPTS}
    assert any(c['slot'] == 48 for c in concepts)
