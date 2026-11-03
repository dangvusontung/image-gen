from app.concept_options import ConceptChoices, apply_choices, style_instruction
from tests.conftest import wait_for_job
from tests.test_concepts_enhancements import propose, render, studio  # noqa: F401


def proposal_brief(**overrides):
    """A brief shaped like one the model proposes, before any user override."""
    return {
        "setting": "a riverside walkway, blue hour",
        "activity": "watching the boats go past",
        "pose": "leaning on the railing",
        "outfit": "a linen shirt with wide cotton trousers",
        "silhouette": "wide cotton trousers",
        "expression": "a quiet half-smile",
        "gaze": "toward the water",
        "camera": "left three-quarter",
        "framing": "three-quarter-body",
        "lighting": "cool ambient light with warm practical lamps",
        **overrides,
    }


def test_user_choices_override_the_proposed_scene_and_outfit(client, studio):
    base, _, _ = studio
    menu = client.get(f"{base}/concept-options")
    assert menu.status_code == 200
    assert ["poolside", "Bên hồ bơi"] in menu.json()["scene"]

    proposals = propose(client, base)
    choices = {"scene": "poolside", "outfit": "denim_shorts", "top": "tee"}
    rendered = render(client, base, proposals[:2], choices=choices)
    assert len(rendered["job_ids"]) == 2

    concepts = client.get(f"{base}/concepts").json()
    for concept in concepts:
        brief = concept["brief"]
        assert "pool" in brief["setting"]
        assert "denim shorts" in brief["outfit"]
        assert "summer daylight" in brief["lighting"]
        assert "User styling choices take priority" in concept["job"]["prompt"]
    assert len({c["brief"]["setting"] for c in concepts}) == 2

    # Regenerating keeps the choices recorded on the original job.
    response = client.post(f"{base}/concepts/{concepts[0]['id']}/regenerate", json={})
    assert response.status_code == 201, response.text
    wait_for_job(client, response.json()["job_ids"][0])
    new = next(c for c in client.get(f"{base}/concepts").json() if c["id"] == response.json()["id"])
    assert "denim shorts" in new["brief"]["outfit"]
    assert "pool" in new["brief"]["setting"]


def test_custom_scene_and_outfit_replace_the_proposal(client, studio):
    base, _, _ = studio
    proposals = propose(client, base)
    for choices in ({"scene": "custom"}, {"outfit": "invalid"}):
        payload = {"proposal_ids": [proposals[0]["id"]], "confirmed": True, "choices": choices}
        assert client.post(f"{base}/concepts/generate", json=payload).status_code in (400, 422)
    assert client.get(f"{base}/concepts").json() == []

    rendered = render(client, base, proposals[:1], choices={
        "scene": "custom", "custom_scene": "a pink rooftop pool", "outfit": "custom",
        "custom_outfit": "a denim skirt and mint blouse", "activity": "holding a lemonade", "lighting": "golden"})
    assert len(rendered["job_ids"]) == 1
    brief = client.get(f"{base}/concepts").json()[0]["brief"]
    assert brief["setting"] == "a pink rooftop pool"
    assert brief["outfit"] == "a denim skirt and mint blouse"
    assert brief["activity"] == "holding a lemonade"
    assert "golden" in brief["lighting"]


def test_denim_mix_rotates_bottoms_and_lighting_overrides_the_proposal():
    outfits = []
    for slot in range(1, 4):
        # denim_mix is no longer the default, so the rotation has to be asked for explicitly.
        brief = apply_choices(proposal_brief(), ConceptChoices(outfit="denim_mix", lighting="daylight"), slot, [])
        outfits.append(brief["outfit"])
        assert "summer daylight" in brief["lighting"]
    assert "denim shorts" in outfits[0]
    assert "denim skirt" in outfits[1]
    assert "pleated skirt" in outfits[2]


def test_glamour_style_changes_direction_without_changing_identity():
    choices = ConceptChoices(style="glamour", scene="poolside", outfit="denim_shorts", top="fitted_tank")
    brief = apply_choices(proposal_brief(), choices, 1, [])
    assert "fitted ribbed tank" in brief["outfit"]
    assert "denim shorts" in brief["outfit"]
    assert "self-assured" in brief["expression"]
    assert "weight shift" in brief["pose"]
    instruction = style_instruction(choices)
    assert "GLAMOUR" in instruction
    assert "Preserve the actual person's face" in instruction
    assert "If the subject is a minor" in instruction


def test_new_outfit_switch_preserves_scene_and_varies_colors():
    for outfit in ['bikini', 'satin_dress', 'satin_pyjamas', 'shirt_shorts', 'bodysuit_trousers', 'offshoulder_skirt']:
        first = apply_choices(proposal_brief(), ConceptChoices(outfit=outfit), 1, [])
        second = apply_choices(proposal_brief(), ConceptChoices(outfit=outfit), 2, [])
        assert first['outfit'] != second['outfit']
        assert first['silhouette'] != 'wide cotton trousers'
        for field in ['setting', 'activity', 'pose', 'gaze', 'camera']:
            assert first[field] == proposal_brief()[field]
    original = proposal_brief(outfit='an opaque teal bikini, barefoot')
    assert apply_choices(original, ConceptChoices(outfit='bikini'), 1, [])['outfit'] == original['outfit']


def test_outfit_switch_is_applied_to_generated_concept_prompt(client, studio):
    base, _, _ = studio
    for outfit, expected in [('satin_dress', 'satin midi slip dress'), ('bikini', 'bikini')]:
        result = client.post(f'{base}/concepts/generate', json={'slots': [67], 'choices': {'outfit': outfit}, 'confirmed': True})
        assert result.status_code == 201, result.text
        job = wait_for_job(client, result.json()['job_ids'][0])
        assert job['status'] == 'succeeded'
        assert expected in job['prompt']
        assert job['meta']['concept_choices']['outfit'] == outfit


def test_black_white_lounge_reference_outfit_is_fixed_and_keeps_scene(client, studio):
    base, _, _ = studio
    options = client.get(f'{base}/concept-options').json()['outfit']
    assert ['black_white_lounge', 'Crop tank + short đen viền trắng'] in options
    result = client.post(f'{base}/concepts/generate', json={'slots': [1, 2], 'choices': {'outfit': 'black_white_lounge'}, 'confirmed': True})
    assert result.status_code == 201, result.text
    for job_id in result.json()['job_ids']:
        job = wait_for_job(client, job_id)
        assert job['status'] == 'succeeded'
        assert 'black fitted cropped tank top' in job['prompt']
        assert 'white drawstring' in job['prompt']
        assert job['meta']['concept_choices']['outfit'] == 'black_white_lounge'
    concepts = client.get(f'{base}/concepts').json()
    assert len({c['brief']['outfit'] for c in concepts}) == 1
    assert all('shorts' in c['brief']['silhouette'] for c in concepts)


def test_white_strapless_dress_changes_only_clothing():
    original = proposal_brief()
    for slot in [1, 117]:
        changed = apply_choices(original, ConceptChoices(outfit='white_strapless_mini'), slot, [])
        assert 'pearl-white satin strapless mini dress' in changed['outfit']
        assert 'white pointed-toe high-heeled pumps' in changed['outfit']
        assert 'strapless mini dress' in changed['silhouette']
        for field in original.keys() - {'outfit', 'silhouette'}:
            assert changed[field] == original[field]


def test_white_strapless_dress_generates_in_original_concept_background(client, studio):
    base, _, _ = studio
    assert ['white_strapless_mini', 'Váy mini satin trắng cúp ngực'] in client.get(f'{base}/concept-options').json()['outfit']
    original = client.get(f'{base}/concept-proposals').json()[0]
    result = client.post(f'{base}/concepts/generate', json={'slots': [1], 'choices': {'outfit': 'white_strapless_mini'}, 'confirmed': True})
    assert result.status_code == 201, result.text
    job = wait_for_job(client, result.json()['job_ids'][0])
    assert job['status'] == 'succeeded'
    assert 'pearl-white satin strapless mini dress' in job['prompt']
    assert original['brief']['setting'] in job['prompt']
    rendered = client.get(f'{base}/concepts').json()[0]['brief']
    assert rendered['setting'] == original['brief']['setting']
    assert rendered['pose'] == original['brief']['pose']
    assert rendered['lighting'] == original['brief']['lighting']


def test_tank_pleated_outfits_keep_background_and_pose():
    from app.outfit_presets import TANK_PLEATED_OUTFITS
    original = proposal_brief()
    for outfit in TANK_PLEATED_OUTFITS:
        result = apply_choices(original, ConceptChoices(outfit=outfit), 1, [])
        assert 'tank top' in result['outfit']
        assert 'pleated' in result['outfit']
        for field in original.keys() - {'outfit', 'silhouette'}:
            assert result[field] == original[field]


def test_tank_pleated_concepts_and_outfit_override_generate(client, studio):
    from app.outfit_presets import TANK_PLEATED_OUTFITS
    base, _, _ = studio
    # Include historical slots when checking the original reference batches.
    defaults = client.get(f'{base}/concept-proposals?include_retired=true').json()
    assert [p['slot'] for p in defaults[117:121]] == [118, 119, 120, 121]
    assert [p['brief']['outfit'] for p in defaults[117:121]] == [v[1] for v in TANK_PLEATED_OUTFITS.values()]
    menu = dict(client.get(f'{base}/concept-options').json()['outfit'])
    assert all(key in menu for key in TANK_PLEATED_OUTFITS)
    for slot, outfit in [(118, 'auto'), (121, 'auto'), (1, 'tank_pleated_sport')]:
        response = client.post(f'{base}/concepts/generate', json={'slots': [slot], 'choices': {'outfit': outfit}, 'confirmed': True})
        assert response.status_code == 201, response.text
        job = wait_for_job(client, response.json()['job_ids'][0])
        assert job['status'] == 'succeeded'
        expected = defaults[slot - 1]['brief']['outfit'] if outfit == 'auto' else TANK_PLEATED_OUTFITS[outfit][1]
        assert expected in job['prompt']
        assert defaults[slot - 1]['brief']['setting'] in job['prompt']
