from app.routes.assets import storage
from tests.conftest import make_image, wait_for_job


def _upload(client, pid, files, kind="reference"):
    return client.post(
        f"/api/projects/{pid}/assets",
        files=[("files", f) for f in files],
        data={"kind": kind},
    )


def test_upload_requires_rights_confirmation(client):
    pid = client.post("/api/projects", json={"name": "P"}).json()["id"]
    resp = _upload(client, pid, [("a.png", make_image(), "image/png")])
    assert resp.status_code == 403
    assert resp.json()["detail"]["code"] == "rights_not_confirmed"


def test_upload_and_download(client, project):
    resp = _upload(client, project, [("ảnh 1.png", make_image(), "image/png"), ("b.jpg", make_image("JPEG"), "image/jpeg")])
    assert resp.status_code == 201
    assets = resp.json()
    assert [a["position"] for a in assets] == [0, 1]
    assert assets[0]["filename"] == "ảnh 1.png"
    assert (assets[0]["width"], assets[0]["height"]) == (64, 48)
    assert assets[1]["content_type"] == "image/jpeg"

    content = client.get(f"/api/assets/{assets[0]['id']}/content")
    assert content.status_code == 200
    assert content.headers["content-type"] == "image/png"
    assert content.content[:8] == b"\x89PNG\r\n\x1a\n"

    listing = client.get("/api/projects").json()
    assert listing[0]["asset_count"] == 2
    assert listing[0]["thumbnail_asset_id"] == assets[0]["id"]


def test_content_type_from_bytes_not_client(client, project):
    resp = _upload(client, project, [("fake.png", make_image("JPEG"), "image/png")])
    assert resp.json()[0]["content_type"] == "image/jpeg"


def test_rejects_corrupt_image(client, project):
    resp = _upload(client, project, [("ok.png", make_image(), "image/png"), ("bad.png", b"not an image", "image/png")])
    assert resp.status_code == 400
    assert resp.json()["detail"]["code"] == "invalid_image"
    assert client.get(f"/api/projects/{project}").json()["assets"] == []


def test_rejects_truncated_image(client, project):
    data = make_image(size=(400, 400))
    resp = _upload(client, project, [("t.png", data[: len(data) // 2], "image/png")])
    assert resp.status_code == 400


def test_rejects_unsupported_format(client, project):
    import io

    from PIL import Image

    buf = io.BytesIO()
    Image.new("RGB", (10, 10)).save(buf, format="GIF")
    resp = _upload(client, project, [("x.gif", buf.getvalue(), "image/gif")])
    assert resp.status_code == 400


def test_filename_traversal_is_sanitized(client, project):
    resp = _upload(client, project, [("../../etc/passwd.png", make_image(), "image/png")])
    asset = resp.json()[0]
    assert asset["filename"] == "passwd.png"
    files = list((storage.base_path / project).iterdir())
    assert len(files) == 1 and files[0].suffix == ".png"


def test_reference_limit(client, project):
    files = [(f"{i}.png", make_image(), "image/png") for i in range(9)]
    resp = _upload(client, project, files)
    assert resp.status_code == 400
    assert resp.json()["detail"]["code"] == "too_many_photos"


def test_side_profile_kind(client, project):
    resp = _upload(client, project, [("side.png", make_image(), "image/png")], kind="side_profile")
    assert resp.json()[0]["kind"] == "side_profile"
    asset_id = resp.json()[0]["id"]
    resp = client.patch(f"/api/assets/{asset_id}", json={"kind": "reference"})
    assert resp.json()["kind"] == "reference"


def test_reorder(client, project):
    ids = [a["id"] for a in _upload(client, project, [(f"{i}.png", make_image(), "image/png") for i in range(3)]).json()]
    resp = client.put(f"/api/projects/{project}/assets/order", json={"asset_ids": ids[::-1]})
    assert resp.status_code == 200
    assert [a["id"] for a in resp.json()] == ids[::-1]
    assert [a["id"] for a in client.get(f"/api/projects/{project}").json()["assets"]] == ids[::-1]

    bad = client.put(f"/api/projects/{project}/assets/order", json={"asset_ids": ids[:2]})
    assert bad.status_code == 400


def test_delete_asset_removes_file(client, project):
    asset = _upload(client, project, [("a.png", make_image(), "image/png")]).json()[0]
    assert len(list((storage.base_path / project).iterdir())) == 1
    assert client.delete(f"/api/assets/{asset['id']}").status_code == 204
    assert list((storage.base_path / project).iterdir()) == []
    assert client.get(f"/api/assets/{asset['id']}/content").status_code == 404


def test_delete_project_removes_files(client, project):
    _upload(client, project, [("a.png", make_image(), "image/png")])
    client.delete(f"/api/projects/{project}")
    assert not (storage.base_path / project).exists()


def test_photos_default_to_selected_and_can_be_deselected(client, project, reference_ids):
    assets = client.get(f"/api/projects/{project}/assets").json()
    assert all(a["selected"] for a in assets), "uploads start in use"

    off = client.patch(f"/api/assets/{reference_ids[0]}", json={"selected": False})
    assert off.status_code == 200 and off.json()["selected"] is False
    # Selection is independent of kind, and a kind-only update leaves it alone.
    kind = client.patch(f"/api/assets/{reference_ids[0]}", json={"kind": "side_profile"})
    assert kind.status_code == 200 and kind.json() == {**off.json(), "kind": "side_profile"}
    assert client.patch(f"/api/assets/{reference_ids[0]}", json={"selected": True}).json()["selected"] is True


def test_only_selected_photos_reach_the_provider(client, project, reference_ids):
    base = f"/api/projects/{project}"
    assert client.patch(f"/api/assets/{reference_ids[0]}", json={"selected": False}).status_code == 200

    estimate = client.get(f"{base}/generation-estimate?purpose=master").json()
    # One photo dropped, plus the built-in art-direction reference every job carries.
    assert estimate["reference_count"] == len(reference_ids) - 1

    result = client.post(f"{base}/master/generate", json={})
    assert result.status_code == 201, result.text
    job = wait_for_job(client, result.json()["job_ids"][0])
    assert job["reference_asset_ids"] == reference_ids[1:]

    # Deselecting everything is a clear refusal, not a request with no references.
    for asset_id in reference_ids:
        client.patch(f"/api/assets/{asset_id}", json={"selected": False})
    refused = client.post(f"{base}/master/generate", json={})
    assert refused.status_code == 400
    assert refused.json()["detail"] == {"code": "references_required", "message": "Chọn ít nhất một ảnh tham chiếu ở bước 1"}
