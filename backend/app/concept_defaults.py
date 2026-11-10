"""Load the editable default concept catalog beside this module."""

from collections.abc import Iterator
from functools import lru_cache
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, model_validator


class CatalogConcept(BaseModel):
    model_config = ConfigDict(extra="forbid")

    slot: int = Field(ge=1, strict=True)
    title: str
    setting: str
    activity: str
    pose: str
    outfit: str
    silhouette: str
    expression: str
    gaze: str
    camera: str
    framing: str
    lighting: str
    footwear: str | None = None


class ConceptCatalog(BaseModel):
    model_config = ConfigDict(extra="forbid")

    concepts: list[CatalogConcept] = Field(min_length=1)
    retired_slots: dict[int, int] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_slots(self) -> "ConceptCatalog":
        slots = sorted(concept.slot for concept in self.concepts)
        if slots != list(range(1, len(slots) + 1)):
            raise ValueError("Concept slots must be unique and contiguous starting at 1.")
        all_slots = set(slots)
        active_slots = all_slots - self.retired_slots.keys()
        if not self.retired_slots.keys() <= all_slots or not set(self.retired_slots.values()) <= active_slots:
            raise ValueError("Each retired slot must exist and point to an active slot.")
        return self


CATALOG_PATH = Path(__file__).with_name("concepts.json")


@lru_cache(maxsize=1)
def _read_catalog(path: Path, stamp: tuple[int, int, int, int]) -> ConceptCatalog:
    return ConceptCatalog.model_validate_json(path.read_text(encoding="utf-8"))


def get_catalog() -> ConceptCatalog:
    stat = CATALOG_PATH.stat()
    return _read_catalog(CATALOG_PATH, (stat.st_ino, stat.st_mtime_ns, stat.st_ctime_ns, stat.st_size))


def catalog_entries(catalog: ConceptCatalog, *, include_retired: bool = False) -> Iterator[tuple[int, dict[str, str]]]:
    for concept in sorted(catalog.concepts, key=lambda concept: concept.slot):
        if include_retired or concept.slot not in catalog.retired_slots:
            yield concept.slot, concept.model_dump(exclude={"slot"}, exclude_none=True)


_CATALOG = get_catalog()

# Slot IDs remain stable even if entries are reordered in JSON.
DEFAULT_CONCEPTS = tuple(brief for _, brief in catalog_entries(_CATALOG, include_retired=True))
RETIRED_CONCEPT_SLOTS = _CATALOG.retired_slots
ACTIVE_DEFAULT_CONCEPTS = tuple(catalog_entries(_CATALOG))
