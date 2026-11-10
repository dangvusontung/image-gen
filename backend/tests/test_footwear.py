import pytest
from pydantic import ValidationError
from app.concept_options import ConceptChoices, apply_choices
from app.concept_defaults import DEFAULT_CONCEPTS
from app.footwear import BLACK_MINI, WHITE_SLINGBACK
from tests.conftest import wait_for_job


def test_footwear_is_independent_of_clothing_and_composition():
    original = DEFAULT_CONCEPTS[130]
    result = apply_choices(original, ConceptChoices(footwear='white_slingback'), 131, [])
    assert result['footwear'] == WHITE_SLINGBACK
    assert all(result[key] == value for key, value in original.items())
    assert ConceptChoices(footwear='white_slingback').overrides_concept()
    assert not ConceptChoices().overrides_concept()
    with pytest.raises(ValidationError):
        ConceptChoices(footwear='custom')
    assert apply_choices(original, ConceptChoices(footwear='custom', custom_footwear='red slingback heels'), 131, [])['footwear'] == 'red slingback heels'


def test_clothing_override_keeps_concept_shoes():
    original = DEFAULT_CONCEPTS[135]
    assert original['outfit'] == BLACK_MINI and original['footwear'] == WHITE_SLINGBACK
    for choices in [ConceptChoices(outfit='satin_dress'), ConceptChoices(outfit='black_strapless_mini')]:
        result = apply_choices(original, choices, 136, [])
        assert result['footwear'] == WHITE_SLINGBACK
        assert result['setting'] == original['setting']
    assert apply_choices(original, ConceptChoices(footwear='barefoot'), 136, [])['outfit'] == BLACK_MINI


def test_garden_cafe_concepts_and_shoe_only_generation(client, project, reference_ids):
    base = f'/api/projects/{project}'
    defaults = client.get(f'{base}/concept-proposals').json()
    assert len(defaults) == 127
    cafe = [p for p in defaults if p['slot'] in (136, 137)]
    assert [p['slot'] for p in cafe] == [136, 137]
    assert cafe[0]['brief']['pose'] != cafe[1]['brief']['pose']
    assert all(p['brief']['footwear'] == WHITE_SLINGBACK for p in cafe)
    result = client.post(f'{base}/master/generate', json={}).json()
    wait_for_job(client, result['job_ids'][0])
    master = client.get(f'{base}/workflow').json()['masters'][0]
    client.post(f"{base}/master/{master['id']}/approve")
    for slot, choices in [(136, {}), (137, {'footwear': 'barefoot'}), (131, {'footwear': 'white_slingback'})]:
        response = client.post(f'{base}/concepts/generate', json={'slots': [slot], 'choices': choices, 'confirmed': True})
        assert response.status_code == 201, response.text
        job = wait_for_job(client, response.json()['job_ids'][0])
        assert job['status'] == 'succeeded'
        original = DEFAULT_CONCEPTS[slot - 1]
        assert original['outfit'] in job['prompt']
        assert original['setting'] in job['prompt']
        assert ('bare feet with no socks' if slot == 137 else WHITE_SLINGBACK) in job['prompt']
        assert 'separate footwear selection overrides' in job['prompt']
