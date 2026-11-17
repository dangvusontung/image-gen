from app.database import SessionLocal
from app.models import ConceptBookmark


def test_catalog_bookmarks_are_global_persistent_and_idempotent(client, project):
    other = client.post('/api/projects', json={'name': 'Another character'}).json()['id']
    first = client.get(f'/api/projects/{project}/concept-proposals').json()
    second = client.get(f'/api/projects/{other}/concept-proposals').json()
    assert first[0]['bookmark_key'] == second[0]['bookmark_key'] == 'default:1'
    assert client.get('/api/concept-bookmarks').json() == {'keys': []}
    url = '/api/concept-bookmarks/default:1'
    for _ in range(2):
        assert client.put(url, json={'bookmarked': True}).status_code == 200
    with SessionLocal() as db:
        assert db.query(ConceptBookmark).count() == 1
    assert client.get('/api/concept-bookmarks').json()['keys'] == ['default:1']
    assert client.delete(f'/api/projects/{project}').status_code == 204
    assert client.get('/api/concept-bookmarks').json()['keys'] == ['default:1']
    for _ in range(2):
        assert client.put(url, json={'bookmarked': False}).status_code == 200
    assert client.get('/api/concept-bookmarks').json()['keys'] == []


def test_invalid_bookmark_keys_do_not_create_rows(client):
    for key in ['default:0', 'default:99999', 'bad-key', 'default:not-a-slot']:
        assert client.put(f'/api/concept-bookmarks/{key}', json={'bookmarked': True}).status_code == 422
    assert client.get('/api/concept-bookmarks').json()['keys'] == []


def test_renaming_and_regenerating_catalog_images_keep_global_bookmark_key(client, project, reference_ids):
    from tests.conftest import wait_for_job

    base = f'/api/projects/{project}'
    master_job = client.post(f'{base}/master/generate', json={}).json()['job_ids'][0]
    assert wait_for_job(client, master_job)['status'] == 'succeeded'
    master = client.get(f'{base}/workflow').json()['masters'][0]
    assert client.post(f"{base}/master/{master['id']}/approve").status_code == 200
    created = client.post(f'{base}/concepts/generate', json={'slots': [160], 'titles': {'160': 'My renamed concept'}})
    assert created.status_code == 201, created.text
    concept_id = created.json()['concept_ids'][0]
    assert wait_for_job(client, created.json()['job_ids'][0])['status'] == 'succeeded'
    row = next(c for c in client.get(f'{base}/concepts').json() if c['id'] == concept_id)
    assert row['bookmark_key'] == 'default:160'
    rerun = client.post(f'{base}/concepts/{concept_id}/regenerate', json={'title': 'Another title'})
    assert rerun.status_code == 201, rerun.text
    row = next(c for c in client.get(f'{base}/concepts').json() if c['id'] == rerun.json()['concept_ids'][0])
    assert row['bookmark_key'] == 'default:160'
