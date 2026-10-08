def test_health(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


def test_list_empty(client):
    assert client.get("/api/projects").json() == []


def test_create_and_get(client):
    resp = client.post("/api/projects", json={"name": "  Test  ", "description": "Mô tả"})
    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == "Test"
    assert data["rights_confirmed"] is False
    assert data["assets"] == []

    got = client.get(f"/api/projects/{data['id']}").json()
    assert got["id"] == data["id"]

    listing = client.get("/api/projects").json()
    assert listing[0]["asset_count"] == 0
    assert listing[0]["thumbnail_asset_id"] is None


def test_create_rejects_empty_name(client):
    assert client.post("/api/projects", json={"name": ""}).status_code == 422


def test_update(client):
    pid = client.post("/api/projects", json={"name": "A"}).json()["id"]
    resp = client.patch(f"/api/projects/{pid}", json={"name": "B", "rights_confirmed": True})
    assert resp.status_code == 200
    assert resp.json()["name"] == "B"
    assert resp.json()["rights_confirmed"] is True
    assert resp.json()["description"] is None


def test_delete(client):
    pid = client.post("/api/projects", json={"name": "X"}).json()["id"]
    assert client.delete(f"/api/projects/{pid}").status_code == 204
    resp = client.get(f"/api/projects/{pid}")
    assert resp.status_code == 404
    assert resp.json()["detail"]["code"] == "project_not_found"


def test_providers(client):
    data = client.get("/api/providers").json()
    assert data[0]["name"] == "mock"
    assert data[0]["enabled"] is True
