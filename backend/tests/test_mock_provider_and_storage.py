import asyncio
import io

import pytest
from PIL import Image

from app.providers.base import CapabilityError, ImageRequest, ReferenceImage, SubmissionState
from app.providers.mock import MockProvider, size_for_aspect
from app.storage.images import MAX_REFERENCE_SIDE, prepare_reference
from app.storage.local import LocalStorage
from app.storage.validation import sanitize_filename
from tests.conftest import make_image


def test_mock_submit_then_poll_returns_png_for_aspect_ratio():
    provider = MockProvider(delay_seconds=0)
    refs = [ReferenceImage(make_image(), "image/png", f"reference {i}") for i in range(3)]

    async def run():
        sub = await provider.submit(ImageRequest(model="mock-v1", prompt="xin chào", references=refs, aspect_ratio="3:4"))
        assert sub.state == SubmissionState.PENDING and sub.polling_url.startswith("mock://")
        return await provider.poll(sub)

    result = asyncio.run(run())
    assert result.state == SubmissionState.READY
    img = Image.open(io.BytesIO(result.images[0].data))
    assert img.format == "PNG"
    assert img.size == size_for_aspect("3:4") == (768, 1024)


def test_mock_poll_after_restart_still_resolves():
    async def run():
        sub = await MockProvider(delay_seconds=0).submit(ImageRequest(model="mock-v1", prompt="x"))
        return await MockProvider().poll(sub)  # fresh instance = process restart

    assert asyncio.run(run()).state == SubmissionState.READY


def test_capability_check_refuses_instead_of_dropping_references():
    provider = MockProvider()
    with pytest.raises(CapabilityError) as exc:
        provider.check_request("mock-small-refs", 3, "1:1")
    assert exc.value.code == "reference_limit_exceeded"
    with pytest.raises(CapabilityError) as exc:
        provider.check_request("mock-small-refs", 1, "21:9")
    assert exc.value.code == "unsupported_aspect_ratio"
    with pytest.raises(CapabilityError):
        provider.check_request("nope", 0, "1:1")


def test_prepare_reference_applies_exif_rotation_strips_metadata_and_caps_size():
    img = Image.new("RGB", (4000, 1000), (10, 20, 30))
    exif = Image.Exif()
    exif[0x0112] = 6  # Orientation: rotate 90° CW to display
    exif[0x8825] = {2: (21.0, 1.0, 0.0)}  # GPSInfo
    buf = io.BytesIO()
    img.save(buf, format="JPEG", exif=exif)

    data, mime = prepare_reference(buf.getvalue())
    out = Image.open(io.BytesIO(data))
    assert mime == "image/jpeg"
    assert out.size == (MAX_REFERENCE_SIDE // 4, MAX_REFERENCE_SIDE)  # rotated to portrait, then capped
    assert not out.getexif()


def test_storage_rejects_traversal(tmp_path):
    storage = LocalStorage(tmp_path / "assets")
    with pytest.raises(ValueError):
        storage.path_for("../secret.txt")
    with pytest.raises(ValueError):
        storage.save(b"x", "../evil", "png")


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("photo.jpg", "photo.jpg"),
        ("C:\\Users\\a\\b.png", "b.png"),
        ("../../x.png", "x.png"),
        ("a\x00b<>.png", "ab.png"),
        ("", "image"),
        (None, "image"),
        ("..", "image"),
    ],
)
def test_sanitize_filename(raw, expected):
    assert sanitize_filename(raw) == expected
