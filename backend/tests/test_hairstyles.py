import pytest

from app.hairstyles import HAIRSTYLES, hairstyle_direction
from tests.conftest import wait_for_job


def test_reference_hair_has_no_override():
    assert hairstyle_direction('reference', 'ignored') == ''


@pytest.mark.parametrize('style', list(HAIRSTYLES) + ['custom'])
def test_master_hairstyle_snapshot(client, project, reference_ids, style):
    response = client.post(f'/api/projects/{project}/master/generate', json={
        'hairstyle': style, 'custom_hairstyle': 'shoulder-length curls with auburn color',
    })
    assert response.status_code == 201, response.text
    job = wait_for_job(client, response.json()['job_ids'][0])
    assert job['status'] == 'succeeded'
    assert (HAIRSTYLES[style] if style != 'custom' else 'shoulder-length curls with auburn color') in job['prompt']
    assert 'takes precedence' in job['prompt']
    assert job['meta']['hairstyle']['style'] == style
    assert job['reference_asset_ids'] == reference_ids


def test_invalid_hairstyle_requests_do_not_queue(client, project, reference_ids):
    base = f'/api/projects/{project}'
    for body in ({'hairstyle': 'unknown'}, {'hairstyle': 'custom', 'custom_hairstyle': '  '}, {'hairstyle': 'custom', 'custom_hairstyle': 'a' * 501}):
        assert client.post(f'{base}/master/generate', json=body).status_code == 422
    assert client.get(f'{base}/workflow').json()['masters'] == []
