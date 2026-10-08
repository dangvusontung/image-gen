import io
import re
import unicodedata
import warnings
from dataclasses import dataclass
from pathlib import PurePath

from PIL import Image, UnidentifiedImageError

Image.MAX_IMAGE_PIXELS = 50_000_000

ALLOWED_FORMATS = {"JPEG": ("jpg", "image/jpeg"), "PNG": ("png", "image/png"), "WEBP": ("webp", "image/webp")}


class InvalidImage(ValueError):
    pass


@dataclass
class ValidatedImage:
    ext: str
    content_type: str
    width: int
    height: int


def validate_image(data: bytes, max_size: int) -> ValidatedImage:
    if not data:
        raise InvalidImage("File rỗng")
    if len(data) > max_size:
        raise InvalidImage(f"File vượt quá {max_size // (1024 * 1024)}MB")
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(io.BytesIO(data)) as img:
                img.verify()
            with Image.open(io.BytesIO(data)) as img:
                fmt = img.format
                width, height = img.size
                img.load()
    except (UnidentifiedImageError, Image.DecompressionBombError, Image.DecompressionBombWarning, OSError, SyntaxError) as exc:
        raise InvalidImage("File không phải ảnh hợp lệ hoặc bị hỏng") from exc
    if fmt not in ALLOWED_FORMATS:
        raise InvalidImage(f"Định dạng {fmt} không được hỗ trợ (chỉ JPEG, PNG, WEBP)")
    ext, content_type = ALLOWED_FORMATS[fmt]
    return ValidatedImage(ext=ext, content_type=content_type, width=width, height=height)


def sanitize_filename(name: str | None) -> str:
    base = PurePath((name or "").replace("\\", "/")).name
    base = unicodedata.normalize("NFC", base)
    base = re.sub(r"[\x00-\x1f\x7f<>:\"/\\|?*]", "", base).strip(" .")
    return base[:200] or "image"
