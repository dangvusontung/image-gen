import io
import json
import zipfile

import pytest
from PIL import Image, ImageDraw

from app.database import SessionLocal
from app.models import GenerationJob
from app.stickers import encode_webp, sticker_image
from tests.conftest import make_image, wait_for_job


def new_pack(client):
    result = client.post('/api/sticker-packs', json={"name": "Tiny moods", "rights_confirmed": True})
    assert result.status_code == 201, result.text
    pack = result.json()
    upload = client.post(f"/api/projects/{pack['id']}/assets", files=[('files', ('me.png', make_image(), 'image/png'))])
    assert upload.status_code == 201
    return pack


def approve_pack_concept(client, pack, variants=1):
    response = client.post(f"/api/sticker-packs/{pack['id']}/concepts/generate", json={"variants": variants, "confirmed": True})
    assert response.status_code == 200, response.text
    jobs = response.json()
    for job in jobs:
        assert wait_for_job(client, job['id'])['status'] == 'succeeded'
    response = client.post(f"/api/sticker-packs/{pack['id']}/concepts/{jobs[0]['id']}/approve")
    assert response.status_code == 200, response.text
    return response.json()


def generated_pack(client, count=3):
    pack = approve_pack_concept(client, new_pack(client))
    ids = [i['id'] for i in pack['items'][:count]]
    result = client.post(f"/api/sticker-packs/{pack['id']}/generate", json={"item_ids": ids})
    assert result.status_code == 200, result.text
    for job in result.json():
        assert wait_for_job(client, job['id'])['status'] == 'succeeded'
    return client.get(f"/api/sticker-packs/{pack['id']}").json(), ids


def test_pack_generation_export_and_isolation(client):
    pack, ids = generated_pack(client)
    assert not any(p['id'] == pack['id'] for p in client.get('/api/projects').json())
    assert client.get('/api/sticker-packs').json()[0]['id'] == pack['id']
    assert len(pack['jobs']) == 3
    assert client.get('/api/gallery').json()['total'] == 0
    assert client.get('/api/jobs').json() == []
    assert len(client.get('/api/jobs?purpose=sticker').json()) == 3
    preview = client.get(f"/api/sticker-packs/{pack['id']}/stickers/{ids[0]}/image")
    assert preview.status_code == 200, preview.text
    assert Image.open(io.BytesIO(preview.content)).size == (512, 512)
    for platform in ('whatsapp', 'telegram'):
        response = client.post(f"/api/sticker-packs/{pack['id']}/export", json={"platform": platform, "item_ids": ids})
        assert response.status_code == 200, response.text
        archive = zipfile.ZipFile(io.BytesIO(response.content))
        metadata = json.loads(archive.read('contents.json'))['sticker_packs'][0]
        assert metadata['name'] == 'Tiny moods'
        assert len(metadata['stickers']) == 3
        for entry in metadata['stickers']:
            data = archive.read(entry['image_file'])
            assert len(data) <= (100 if platform == 'whatsapp' else 512) * 1024
            image = Image.open(io.BytesIO(data))
            assert image.size == (512, 512)
            assert image.convert('RGBA').getchannel('A').getextrema()[0] == 0
        assert Image.open(io.BytesIO(archive.read('tray.png'))).size == (96, 96)
        assert len(archive.read('tray.png')) <= 50 * 1024
        assert 'IMPORT.txt' in archive.namelist()
    # A preview URL cannot borrow a job from a different pack.
    other, other_ids = generated_pack(client, 1)
    job_id = other['jobs'][other_ids[0]]['id']
    assert client.get(f"/api/sticker-packs/{pack['id']}/stickers/{ids[0]}/image?job_id={job_id}").status_code == 409
    assert client.delete(f"/api/projects/{pack['id']}").status_code == 204
    assert client.get(f"/api/sticker-packs/{pack['id']}").status_code == 404


def test_changed_stickers_require_regeneration_and_preserve_jobs(client):
    pack, ids = generated_pack(client, 1)
    old_job = pack['jobs'][ids[0]]['id']
    pack['items'][0]['expression'] = 'A new surprised reaction with both hands raised'
    payload = {k: pack[k] for k in ('name', 'publisher', 'style', 'items')}
    assert client.put(f"/api/sticker-packs/{pack['id']}", json=payload).status_code == 200
    response = client.post(f"/api/sticker-packs/{pack['id']}/export", json={"platform": 'telegram', "item_ids": ids})
    assert response.status_code == 409
    assert response.json()['detail']['code'] == 'sticker_outdated'
    regen = client.post(f"/api/sticker-packs/{pack['id']}/generate", json={"item_ids": ids}).json()[0]
    assert regen['id'] != old_job
    assert wait_for_job(client, regen['id'])['status'] == 'succeeded'
    assert client.get(f"/api/jobs/{old_job}").json()['status'] == 'succeeded'
    assert client.get(f"/api/sticker-packs/{pack['id']}").json()['jobs'][ids[0]]['id'] == regen['id']


def test_pack_validation_and_export_requirements(client):
    pack = new_pack(client)
    base = f"/api/sticker-packs/{pack['id']}"
    assert client.post(f'{base}/generate', json={"item_ids": ['not-here']}).status_code == 400
    assert client.post(f'{base}/export', json={"platform": 'whatsapp', "item_ids": ['hello']}).status_code == 400
    assert client.post(f'{base}/export', json={"platform": 'telegram', "item_ids": ['hello']}).status_code == 409
    assert client.post(f'{base}/generate', json={"item_ids": []}).status_code == 422
    assert client.post('/api/sticker-packs', json={"name": '   '}).status_code == 422
    item = pack['items'][0]
    assert client.put(base, json={"items": [item, item]}).status_code == 422
    assert client.get(f'{base}/estimate?count=0').status_code == 400
    approve_pack_concept(client, pack)
    client.patch(f"/api/projects/{pack['id']}", json={"rights_confirmed": False})
    assert client.post(f'{base}/generate', json={"item_ids": ['hello']}).status_code == 403


def test_rejected_bulk_leaves_no_jobs(client):
    pack = approve_pack_concept(client, new_pack(client))
    from app.main import app
    from app.providers.mock import MockProvider
    # Paid-provider semantics without any network traffic.
    provider = MockProvider()
    provider.name = 'paid-sticker-test'
    from app.providers.registry import ProviderRegistry
    app.state.registry = ProviderRegistry([*app.state.registry.all(), provider])
    client.patch(f"/api/projects/{pack['id']}", json={"provider": provider.name})
    response = client.post(f"/api/sticker-packs/{pack['id']}/generate", json={"item_ids": ['hello', 'love']})
    assert response.status_code == 400
    assert response.json()['detail']['code'] == 'bulk_confirmation_required'
    with SessionLocal() as db:
        assert db.query(GenerationJob).filter_by(project_id=pack['id'], purpose='sticker').count() == 0


def test_existing_character_is_copied_into_pack(client, project, reference_ids):
    result = client.post(f'/api/projects/{project}/master/generate', json={"variants": 1}).json()
    assert wait_for_job(client, result['job_ids'][0])['status'] == 'succeeded'
    master = client.get(f'/api/projects/{project}/workflow').json()['masters'][0]
    client.post(f"/api/projects/{project}/master/{master['id']}/approve")
    response = client.post('/api/sticker-packs', json={"source_project_id": project, "rights_confirmed": True})
    assert response.status_code == 201, response.text
    pack = response.json()
    ref = pack['project']['assets'][0]
    assert ref['id'] not in reference_ids
    assert client.delete(f'/api/projects/{project}').status_code == 204
    assert client.get(f"/api/assets/{ref['id']}/content").status_code == 200
    pack = approve_pack_concept(client, pack)
    response = client.post(f"/api/sticker-packs/{pack['id']}/generate", json={"item_ids": ['hello']})
    assert response.status_code == 200
    assert wait_for_job(client, response.json()[0]['id'])['status'] == 'succeeded'


def test_background_removal_preserves_subject_and_alpha():
    image = Image.new('RGB', (768, 600), '#ff00ff')
    ImageDraw.Draw(image).ellipse((200, 100, 550, 500), fill='#ffc85c')
    raw = io.BytesIO(); image.save(raw, format='PNG')
    output = sticker_image(raw.getvalue())
    assert output.size == (512, 512)
    assert output.getpixel((0, 0))[3] == 0
    assert output.getpixel((256, 256))[3] == 255
    assert len(encode_webp(output, 100 * 1024)) <= 100 * 1024
    with pytest.raises(ValueError, match='magenta background'):
        sticker_image(make_image())


def test_dialogue_edits_reuse_artwork_and_match_draft_preview(client):
    pack, ids = generated_pack(client, 1)
    item = pack['items'][0]
    job = pack['jobs'][ids[0]]
    assert job['meta']['artwork_version'] == 2
    assert item['caption'] not in job['prompt']
    assert 'Do not draw any text' in job['prompt']
    original = client.get(f"/api/sticker-packs/{pack['id']}/stickers/{ids[0]}/image").content
    for style in ('caption', 'speech', 'thought'):
        item.update(caption='Ủa, thiệt luôn?\nHết cứu!', text_style=style, text_y=.18, text_color='#593994')
        draft = client.post(f"/api/sticker-packs/{pack['id']}/stickers/{ids[0]}/preview", json=item)
        assert draft.status_code == 200, draft.text
        assert draft.content != original
        payload = {k: pack[k] for k in ('name', 'publisher', 'style', 'items')}
        assert client.put(f"/api/sticker-packs/{pack['id']}", json=payload).status_code == 200
        saved = client.get(f"/api/sticker-packs/{pack['id']}/stickers/{ids[0]}/image")
        assert saved.content == draft.content
        assert saved.headers['cache-control'] == 'no-store'
        result = client.post(f"/api/sticker-packs/{pack['id']}/export", json={"platform": 'telegram', "item_ids": ids})
        assert result.status_code == 200, result.text
    state = client.get(f"/api/sticker-packs/{pack['id']}").json()
    assert state['jobs'][ids[0]]['id'] == job['id']
    with SessionLocal() as db:
        assert db.query(GenerationJob).filter_by(project_id=pack['id'], purpose='sticker').count() == 1


def test_legacy_lettering_requires_one_regeneration(client):
    pack, ids = generated_pack(client, 1)
    with SessionLocal() as db:
        job = db.get(GenerationJob, pack['jobs'][ids[0]]['id'])
        job.meta = {k: v for k, v in job.meta.items() if k != 'artwork_version'}
        db.commit()
    result = client.get(f"/api/sticker-packs/{pack['id']}/stickers/{ids[0]}/image")
    assert result.status_code == 409
    assert result.json()['detail']['code'] == 'sticker_outdated'


def test_text_fitting_and_placement_preserve_transparency():
    from app.stickers import caption_font, compose_sticker, text_layout
    base = Image.new('RGBA', (512, 512))
    ImageDraw.Draw(base).ellipse((120, 80, 390, 450), fill='#ffc85c')
    dialogue = 'Ủa, thiệt luôn? Hết cứu! ' * 4
    for style in ('caption', 'speech', 'thought'):
        for x, y in ((0, 0), (1, 1), (.5, .5)):
            output = compose_sticker(base, {'caption': dialogue, 'text_style': style, 'text_x': x, 'text_y': y, 'text_color': '#ffffff'})
            assert output.size == (512, 512)
            assert output.getchannel('A').getextrema() == (0, 255)
            bounds = output.getchannel('A').getbbox()
            assert bounds and 0 < bounds[0] < bounds[2] < 512 and 0 < bounds[1] < bounds[3] < 512
            assert len(encode_webp(output, 100 * 1024)) <= 100 * 1024
    wrapped, font, bounds = text_layout(dialogue, 64, True)
    assert ''.join(wrapped.split()) == ''.join(dialogue.split())
    assert bounds[2] - bounds[0] <= 390
    assert bounds[3] - bounds[1] <= 126
    assert font.size <= 64
    assert bytes(caption_font(48).getmask('ệ')) != bytes(caption_font(48).getmask('□'))


def test_concept_approval_gates_stickers_and_anchors_identity(client):
    pack = new_pack(client)
    base = f"/api/sticker-packs/{pack['id']}"
    assert client.post(f'{base}/generate', json={"item_ids": ['hello']}).json()['detail']['code'] == 'concept_required'
    assert client.get(f'{base}/estimate').status_code == 409
    pack = approve_pack_concept(client, pack, variants=2)
    concept = pack['approved_concept']
    result = client.post(f'{base}/generate', json={"item_ids": ['hello']})
    assert result.status_code == 200, result.text
    job = result.json()[0]
    assert job['reference_asset_ids'] == concept['output_asset_ids'][:1]
    assert job['meta']['concept_job_id'] == concept['id']
    assert wait_for_job(client, job['id'])['status'] == 'succeeded'
    alternative = next(c['job'] for c in pack['concepts'] if c['job']['id'] != concept['id'])
    assert client.post(f"{base}/concepts/{alternative['id']}/approve").status_code == 200
    assert client.post(f'{base}/export', json={"platform": 'telegram', "item_ids": ['hello']}).json()['detail']['code'] == 'sticker_outdated'
    other = new_pack(client)
    assert client.post(f"/api/sticker-packs/{other['id']}/concepts/{concept['id']}/approve").status_code == 404


def test_changed_photos_style_and_brief_invalidate_concept(client):
    pack = approve_pack_concept(client, new_pack(client))
    base = f"/api/sticker-packs/{pack['id']}"
    previous = pack['approved_concept']['id']
    client.post(f"/api/projects/{pack['id']}/assets", files=[('files', ('new.png', make_image(), 'image/png'))])
    assert client.get(base).json()['approved_concept'] is None
    assert client.post(f'{base}/concepts/{previous}/approve').status_code == 409
    pack = approve_pack_concept(client, client.get(base).json())
    payload = {k: pack[k] for k in ('name', 'publisher', 'style', 'items', 'concept_brief')}
    payload['concept_brief'] = 'A new outfit and hairstyle'
    result = client.put(base, json=payload)
    assert result.status_code == 200
    assert result.json()['approved_concept'] is None
    assert not any(c['current'] for c in result.json()['concepts'])
    pack = approve_pack_concept(client, result.json())
    payload['style'] = 'comic'
    result = client.put(base, json=payload)
    assert result.status_code == 200
    assert result.json()['approved_concept'] is None
    assert client.post(f"{base}/concepts/{pack['approved_concept']['id']}/approve").status_code == 409
