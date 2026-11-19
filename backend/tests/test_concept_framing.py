import json

from app import concept_defaults
from app.concept_options import FULL_BODY_FRAMING
from tests.conftest import wait_for_job
from tests.test_concepts_enhancements import propose, render, studio  # noqa: F401


def assert_full_body(job):
    assert job["meta"]["full_body"] is True
    assert job["meta"]["brief"]["framing"] == FULL_BODY_FRAMING
    assert "clear space above the head and below the soles" in job["prompt"]
    assert "both shoes fully visible when worn" in job["prompt"]
    assert job["prompt"].count("FULL-BODY FRAMING — REQUIRED") == 1


def test_full_body_catalog_slots_render_with_master_outfit(client, studio):
    base, _, _ = studio
    catalog = client.get(f"{base}/concept-proposals").json()
    full_body = [row for row in catalog if row["group"] == "Toàn thân"]
    assert [row["slot"] for row in full_body] == [191, 192, 193, 194]
    assert sorted(row["display_number"] for row in full_body) == [160, 161, 162, 163]
    result = render(client, base, slots=[191, 192, 193, 194], choices={"outfit": "master"})
    for job_id in result["job_ids"]:
        job = wait_for_job(client, job_id)
        assert_full_body(job)
        assert job["meta"]["master_outfit"] is True
        assert "footwear" not in job["meta"]["brief"]
        assert "Keep the exact outfit from the approved MASTER" in job["prompt"]

    old = wait_for_job(client, result["job_ids"][0])
    regenerated = client.post(f"{base}/concepts/{result['concept_ids'][0]}/regenerate", json={"prompt_mode": "saved"})
    assert regenerated.status_code == 201, regenerated.text
    job = wait_for_job(client, regenerated.json()["job_ids"][0])
    assert_full_body(job)
    assert job["prompt"] == old["prompt"]

    edited = "An eye-level portrait on a quiet platform."
    regenerated = client.post(f"{base}/concepts/{result['concept_ids'][0]}/regenerate", json={"prompt": edited})
    assert regenerated.status_code == 201, regenerated.text
    job = wait_for_job(client, regenerated.json()["job_ids"][0])
    assert_full_body(job)
    assert job["prompt"].startswith(edited + "\n")


def test_full_body_proposals_custom_and_regeneration(client, studio):
    base, _, _ = studio
    custom = render(client, base, custom=True, choices={"scene": "garden", "full_body": True})
    assert_full_body(wait_for_job(client, custom["job_ids"][0]))

    proposals = propose(client, base)
    full_body = [row for row in proposals if row["brief"]["framing"] == FULL_BODY_FRAMING]
    assert len(full_body) == 4
    # Mock proposal 1 collides with a non-full-body catalog slot.
    proposal = render(client, base, full_body[:1])
    job = wait_for_job(client, proposal["job_ids"][0])
    assert_full_body(job)

    regenerated = client.post(f"{base}/concepts/{proposal['concept_ids'][0]}/regenerate", json={"prompt_mode": "current"})
    assert regenerated.status_code == 201, regenerated.text
    assert_full_body(wait_for_job(client, regenerated.json()["job_ids"][0]))

    legacy = render(client, base, [next(row for row in proposals if row["brief"]["framing"] == "three-quarter-body")])
    job = wait_for_job(client, legacy["job_ids"][0])
    assert job["meta"]["brief"]["framing"] == "three-quarter-body"
    assert "FULL-BODY FRAMING" not in job["prompt"]


def test_old_custom_slot_is_not_replaced_by_new_catalog_entry(client, studio, tmp_path, monkeypatch):
    base, _, _ = studio
    old_catalog_path = tmp_path / "old_catalog.json"
    catalog = json.loads(concept_defaults.CATALOG_PATH.read_text(encoding="utf-8"))
    catalog["concepts"] = catalog["concepts"][:190]
    old_catalog_path.write_text(json.dumps(catalog), encoding="utf-8")
    with monkeypatch.context() as patch:
        patch.setattr(concept_defaults, "CATALOG_PATH", old_catalog_path)
        custom = render(client, base, custom=True, choices={"scene": "custom", "custom_scene": "an old studio"})
    old = wait_for_job(client, custom["job_ids"][0])
    assert old["meta"]["slot"] == 191
    for response in (
        client.post(f"{base}/concepts/{custom['concept_ids'][0]}/regenerate", json={"prompt_mode": "current"}),
        client.post(f"{base}/concepts/generate", json={
            "source_run": old["meta"]["run"], "slots": [191], "use_catalog_briefs": True,
        }),
    ):
        assert response.status_code == 201, response.text
        job = wait_for_job(client, response.json()["job_ids"][0])
        assert job["meta"]["brief"]["setting"] == "an old studio"
        assert job["meta"]["brief"]["framing"] == "three-quarter-body"
        assert "FULL-BODY FRAMING" not in job["prompt"]
