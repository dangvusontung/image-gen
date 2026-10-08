import io

from PIL import Image, ImageOps

MAX_REFERENCE_SIDE = 2048


def prepare_reference(data: bytes) -> tuple[bytes, str]:
    """Normalize an image before it leaves the machine: apply EXIF rotation, cap size, drop metadata (GPS etc.)."""
    with Image.open(io.BytesIO(data)) as img:
        img = ImageOps.exif_transpose(img)
        img.thumbnail((MAX_REFERENCE_SIDE, MAX_REFERENCE_SIDE), Image.Resampling.LANCZOS)
        buf = io.BytesIO()
        if img.mode in ("RGBA", "LA") or (img.mode == "P" and "transparency" in img.info):
            img.save(buf, format="PNG", optimize=True)
            return buf.getvalue(), "image/png"
        img.convert("RGB").save(buf, format="JPEG", quality=92)
        return buf.getvalue(), "image/jpeg"
