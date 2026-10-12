"""Reference images shipped with the app, used without any upload or selection.

They are addressed as "builtin:<name>" wherever a job lists its reference asset ids; the job
runner resolves those straight from disk instead of the project's own assets.
"""

from functools import lru_cache
from pathlib import Path

from PIL import Image

BUILTIN_PREFIX = "builtin:"
_DIR = Path(__file__).parent

#: name -> (file, label sent to the provider)
BUILTIN_REFERENCES = {
    "concept_reference": (
        _DIR / "concept_reference.jpg",
        "STYLE TEMPLATE, art direction only",
    ),
}

#: The app's fixed art-direction reference, used by every step unless a project overrides it.
DEFAULT_REFERENCE_ID = BUILTIN_PREFIX + "concept_reference"


def is_builtin(asset_id: str) -> bool:
    return asset_id.startswith(BUILTIN_PREFIX)


def builtin_reference(asset_id: str) -> tuple[Path, str] | None:
    entry = BUILTIN_REFERENCES.get(asset_id.removeprefix(BUILTIN_PREFIX))
    return entry if entry and entry[0].is_file() else None


@lru_cache(maxsize=None)
def builtin_size(asset_id: str) -> tuple[int, int]:
    """Pixel size of a built-in reference, for input-priced cost estimates."""
    entry = builtin_reference(asset_id)
    if entry is None:
        return (2048, 2048)
    with Image.open(entry[0]) as image:
        return image.size
