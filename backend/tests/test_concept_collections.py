import json

import pytest
from pydantic import ValidationError

from app import concept_defaults
from tests.conftest import wait_for_job
from tests.test_concepts_enhancements import render, studio  # noqa: F401


def test_collection_metadata_is_independent_of_scene_and_pose(client, project):
    rows = client.get(f"/api/projects/{project}/concept-proposals").json()
    collection = [row for row in rows if row["collection_id"] == "bamboo-poolside"]
    assert [row["slot"] for row in collection] == list(range(195, 201))
    assert {row["collection_name"] for row in collection} == {"Hồ bơi tre xanh"}
    assert {row["group"] for row in collection} == {"Bể bơi"}
    assert len({row["family"] for row in collection}) == 3
    for row in collection:
        assert row["bookmark_key"] == f"default:{row['slot']}"
        assert row["id"] == f"default-{row['slot']}"
        assert "collection_id" not in row["brief"]
        assert "collection_name" not in row["brief"]
    assert all(row["collection_id"] is None for row in rows if row["slot"] < 195 and row["group"] != "Biển" and row["slot"] != 92)


def test_collection_can_render_as_a_batch_without_changing_the_brief(client, studio):
    base, _, _ = studio
    result = render(client, base, slots=list(range(195, 201)))
    assert len(result["job_ids"]) == 6
    for job_id in result["job_ids"]:
        job = wait_for_job(client, job_id)
        assert job["status"] == "succeeded"
        assert "collection_id" not in job["meta"]["brief"]
    rows = client.get(f"{base}/concepts").json()
    selected = [row for row in rows if row["id"] in result["concept_ids"]]
    assert len(selected) == 6
    assert {row["collection_id"] for row in selected} == {"bamboo-poolside"}
    assert {row["collection_name"] for row in selected} == {"Hồ bơi tre xanh"}


def test_catalog_rejects_duplicate_and_unknown_collection_ids():
    source = json.loads(concept_defaults.CATALOG_PATH.read_text(encoding="utf-8"))
    duplicate = json.loads(json.dumps(source))
    duplicate["collections"].append(duplicate["collections"][0].copy())
    with pytest.raises(ValidationError, match="Collection IDs must be unique"):
        concept_defaults.ConceptCatalog.model_validate(duplicate)
    source["concepts"][-1]["collection_id"] = "missing-collection"
    with pytest.raises(ValidationError, match="known collection"):
        concept_defaults.ConceptCatalog.model_validate(source)


def test_old_catalog_without_collections_remains_valid():
    source = json.loads(concept_defaults.CATALOG_PATH.read_text(encoding="utf-8"))
    source.pop("collections")
    for concept in source["concepts"]:
        concept.pop("collection_id", None)
    catalog = concept_defaults.ConceptCatalog.model_validate(source)
    assert catalog.collections == []
    assert all(row["collection_name"] == "" for row in concept_defaults.catalog_presentation(catalog).values())


def test_custom_image_with_a_reused_slot_does_not_join_the_new_collection(client, studio, tmp_path, monkeypatch):
    base, _, _ = studio
    source = json.loads(concept_defaults.CATALOG_PATH.read_text(encoding="utf-8"))
    source["concepts"] = source["concepts"][:194]
    path = tmp_path / "old-catalog.json"
    path.write_text(json.dumps(source), encoding="utf-8")
    with monkeypatch.context() as patch:
        patch.setattr(concept_defaults, "CATALOG_PATH", path)
        result = render(client, base, custom=True, choices={"scene": "studio"})
    assert wait_for_job(client, result["job_ids"][0])["meta"]["slot"] == 195
    row = next(row for row in client.get(f"{base}/concepts").json() if row["id"] == result["concept_ids"][0])
    assert row["collection_id"] is None
    assert row["collection_name"] == ""


def test_beach_collection_contains_all_beach_concepts_and_new_references(client, project):
    rows = client.get(f"/api/projects/{project}/concept-proposals?include_retired=true").json()
    beach = [row for row in rows if row["collection_id"] == "beach"]
    assert {row["slot"] for row in beach} == {49, 50, 51, 52, 92, 129, 164, 166, 210}
    assert {row["collection_name"] for row in beach} == {"Beach · Biển"}
    assert all(row["collection_id"] == "beach" for row in rows if row["group"] == "Biển")
    first = next(row for row in rows if row["slot"] == 209)
    assert "kneeling" in first["brief"]["pose"]
    assert "feather" in first["brief"]["outfit"]
    second = next(row for row in beach if row["slot"] == 210)
    assert "platform flip-flops" in second["brief"]["outfit"]
    assert "coconut palms" in second["brief"]["setting"]
