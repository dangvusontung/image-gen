import asyncio
import io

import pytest
from PIL import Image

from app.providers.mock import MockProvider
from app.storage.local import LocalStorage
from app.storage.validation import sanitize_filename


def test_mock_provider_returns_png_of_requested_size():
    data = asyncio.run(MockProvider().generate_image("hello", [], width=300, height=400))
    img = Image.open(io.BytesIO(data))
    assert img.format == "PNG"
    assert img.size == (300, 400)


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
