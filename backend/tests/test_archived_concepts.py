from app.concept_defaults import get_catalog
from tests.test_concepts_enhancements import propose, render, studio  # noqa: F401


def test_archive_flags_replacements_and_explicit_rendering(client, studio):
    base, _, _ = studio
    active = client.get(f"{base}/concept-proposals").json()
    all_rows = client.get(f"{base}/concept-proposals?include_retired=true").json()
    archived = [row for row in all_rows if row["archived"]]
    assert {row["slot"] for row in archived} == set(get_catalog().retired_slots)
    assert not any(row["archived"] for row in active)
    slot156 = next(row for row in archived if row["slot"] == 156)
    assert slot156["replacement_slot"] == 155
    assert slot156["display_number"] is None
    result = render(client, base, slots=[156])
    row = next(row for row in client.get(f"{base}/concepts").json() if row["id"] == result["concept_ids"][0])
    assert row["archived"] is True
    assert row["replacement_slot"] == 155
    assert "archived" not in row["brief"]


def test_archive_catalog_is_available_after_ai_proposals(client, studio):
    base, _, _ = studio
    proposals = propose(client, base)
    assert [row["id"] for row in client.get(f"{base}/concept-proposals").json()] == [row["id"] for row in proposals]
    catalog = client.get(f"{base}/concept-proposals?include_retired=true").json()
    assert len(catalog) == len(get_catalog().concepts)
    assert all(row["run"] == 0 for row in catalog)
    assert any(row["slot"] == 156 and row["archived"] for row in catalog)


def test_database_archive_changes_are_shared_and_not_overwritten_by_json(client, project):
    base = f'/api/projects/{project}'
    response = client.patch(f'{base}/concept-catalog/208', json={'archived': True})
    assert response.status_code == 200, response.text
    other = client.post('/api/projects', json={'name': 'Other'}).json()['id']
    other_base = f'/api/projects/{other}'
    assert 208 not in {row['slot'] for row in client.get(f'{other_base}/concept-proposals?status=active').json()}
    assert 208 in {row['slot'] for row in client.get(f'{other_base}/concept-proposals?status=archived').json()}
    assert client.patch(f'{base}/concept-catalog/208', json={'archived': False}).status_code == 200
    assert 208 in {row['slot'] for row in client.get(f'{base}/concept-proposals?status=active').json()}
    assert client.patch(f'{base}/concept-catalog/155', json={'archived': True}).status_code == 409
    assert client.patch(f'{base}/concept-catalog/156', json={'archived': False}).status_code == 200
    assert 156 not in {row['slot'] for row in client.get(f'{base}/concept-proposals?status=archived').json()}
    assert client.patch(f'{base}/concept-catalog/208', json={'archived': True, 'replacement_slot': 208}).status_code == 422
