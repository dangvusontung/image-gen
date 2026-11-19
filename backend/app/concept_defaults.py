"""Load the editable default concept catalog beside this module."""

from collections.abc import Iterator
from functools import lru_cache
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, model_validator

CONCEPT_GROUPS = (
    "Phòng khách & sinh hoạt", "Phòng ngủ & nghỉ ngơi", "Bếp & bên cửa sổ",
    "Phòng tắm", "Làm đẹp & công việc", "Café", "Bể bơi", "Biển",
    "Ngoài trời & du lịch", "Việt Nam", "Thời trang & ánh đèn",
    "Studio & chân dung", "Gym", "Yoga", "Toàn thân",
)
PRESENTATION_FIELDS = {"label", "group", "family", "tags", "collection_id"}


class ConceptCollection(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$", max_length=80)
    name: str = Field(min_length=1, max_length=120)
    description: str = ""


class CatalogConcept(BaseModel):
    model_config = ConfigDict(extra="forbid")

    slot: int = Field(ge=1, strict=True)
    title: str
    label: str = Field(min_length=1)
    group: str = Field(min_length=1)
    family: str = Field(min_length=1)
    tags: list[str] = Field(min_length=1)
    collection_id: str | None = None
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

    collections: list[ConceptCollection] = Field(default_factory=list)
    concepts: list[CatalogConcept] = Field(min_length=1)
    retired_slots: dict[int, int] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_slots(self) -> "ConceptCatalog":
        if any(concept.group not in CONCEPT_GROUPS for concept in self.concepts):
            raise ValueError("Every concept must belong to a known scene group.")
        collection_ids = [collection.id for collection in self.collections]
        if len(collection_ids) != len(set(collection_ids)):
            raise ValueError("Collection IDs must be unique.")
        if any(concept.collection_id is not None and concept.collection_id not in collection_ids
               for concept in self.concepts):
            raise ValueError("Every collection_id must reference a known collection.")
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
            yield concept.slot, concept.model_dump(exclude={"slot", *PRESENTATION_FIELDS}, exclude_none=True)


def catalog_presentation(catalog: ConceptCatalog) -> dict[int, dict]:
    """Picker metadata stays separate from generation briefs and stable slot IDs."""
    active = sorted(
        (row for row in catalog.concepts if row.slot not in catalog.retired_slots),
        key=lambda row: (CONCEPT_GROUPS.index(row.group), row.family, row.slot),
    )
    numbers = {row.slot: number for number, row in enumerate(active, start=1)}
    collection_names = {collection.id: collection.name for collection in catalog.collections}
    return {
        row.slot: {
            **row.model_dump(include=PRESENTATION_FIELDS),
            "collection_name": collection_names.get(row.collection_id, ""),
            "archived": row.slot in catalog.retired_slots,
            "replacement_slot": catalog.retired_slots.get(row.slot),
            "catalog_code": f"C{row.slot:03d}",
            "display_number": numbers.get(row.slot),
        }
        for row in catalog.concepts
    }


_CATALOG = get_catalog()

# Slot IDs remain stable even if entries are reordered in JSON.
DEFAULT_CONCEPTS = tuple(brief for _, brief in catalog_entries(_CATALOG, include_retired=True))
RETIRED_CONCEPT_SLOTS = _CATALOG.retired_slots
ACTIVE_DEFAULT_CONCEPTS = tuple(catalog_entries(_CATALOG))
