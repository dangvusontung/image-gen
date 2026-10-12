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
