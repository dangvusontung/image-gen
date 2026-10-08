from app.concept_options import ConceptChoices, apply_choices, style_instruction
from app.concept_planning import fresh_brief
from tests.conftest import wait_for_job
from tests.test_concepts_enhancements import studio  # noqa: F401


def test_poolside_menu_partial_batch_and_regeneration(client, studio):
    base, _, _ = studio
    menu = client.get(f"{base}/concept-options")
    assert menu.status_code == 200
    assert ["poolside", "Bên hồ bơi"] in menu.json()["scene"]
    choices = {"scene": "poolside", "outfit": "denim_shorts", "top": "tee"}
    response = client.post(f"{base}/concepts/generate", json={"batch": "A", "count": 2, "choices": choices})
    assert response.status_code == 201, response.text
    assert len(response.json()["job_ids"]) == 2
    for job_id in response.json()["job_ids"]:
        assert wait_for_job(client, job_id)["status"] == "succeeded"
    concepts = client.get(f"{base}/concepts").json()
    for concept in concepts:
        brief = concept["brief"]
        assert "pool" in brief["setting"]
        assert "denim shorts" in brief["outfit"]
        assert "summer daylight" in brief["lighting"]
        assert "User styling choices take priority" in concept["job"]["prompt"]
    assert len({c["brief"]["setting"] for c in concepts}) == 2
    concept = concepts[0]
    response = client.post(f"{base}/concepts/{concept['id']}/regenerate", json={})
    assert response.status_code == 201, response.text
    wait_for_job(client, response.json()["job_ids"][0])
    new = next(c for c in client.get(f"{base}/concepts").json() if c["id"] == response.json()["id"])
    assert "denim shorts" in new["brief"]["outfit"]
    assert "pool" in new["brief"]["setting"]


def test_custom_scene_outfit_and_validation(client, studio):
    base, _, _ = studio
    for payload in ({"batch": "B", "count": 5}, {"batch": "A", "choices": {"scene": "custom"}}, {"batch": "A", "choices": {"outfit": "invalid"}}):
        assert client.post(f"{base}/concepts/generate", json=payload).status_code in (400, 422)
    assert client.get(f"{base}/concepts").json() == []
    response = client.post(f"{base}/concepts/generate", json={"batch": "B", "count": 1, "choices": {
        "scene": "custom", "custom_scene": "a pink rooftop pool", "outfit": "custom", "custom_outfit": "a denim skirt and mint blouse", "activity": "holding a lemonade", "lighting": "golden"}})
    assert response.status_code == 201, response.text
    wait_for_job(client, response.json()["job_ids"][0])
    brief = client.get(f"{base}/concepts").json()[0]["brief"]
    assert brief["setting"] == "a pink rooftop pool"
    assert brief["outfit"] == "a denim skirt and mint blouse"
    assert brief["activity"] == "holding a lemonade"
    assert "golden" in brief["lighting"]


def test_preferred_mix_and_lighting_override():
    outfits = []
    for slot in range(1, 4):
        brief = apply_choices(fresh_brief([], slot, "front"), ConceptChoices(lighting="daylight"), slot, [])
        outfits.append(brief["outfit"])
        assert "autumn" not in brief["setting"] and "winter" not in brief["setting"]
    assert "denim shorts" in outfits[0]
    assert "denim skirt" in outfits[1]
    assert "pleated skirt" in outfits[2]


def test_glamour_style_changes_direction_without_changing_identity():
    choices = ConceptChoices(style="glamour", scene="poolside", outfit="denim_shorts", top="fitted_tank")
    brief = apply_choices(fresh_brief([], 1, "front-facing"), choices, 1, [])
    assert "fitted ribbed tank" in brief["outfit"]
    assert "denim shorts" in brief["outfit"]
    assert "self-assured" in brief["expression"]
    assert "weight shift" in brief["pose"]
    instruction = style_instruction(choices)
    assert "GLAMOUR" in instruction
    assert "Preserve the actual person's face" in instruction
    assert "If the subject is a minor" in instruction
