"""Load the editable default concept catalog beside this module."""

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


_CATALOG = ConceptCatalog.model_validate_json(Path(__file__).with_name("concepts.json").read_text(encoding="utf-8"))

# Slot IDs remain stable even if entries are reordered in JSON.
DEFAULT_CONCEPTS = tuple(
    concept.model_dump(exclude={"slot"}, exclude_none=True)
    for concept in sorted(_CATALOG.concepts, key=lambda concept: concept.slot)
)
RETIRED_CONCEPT_SLOTS = _CATALOG.retired_slots
ACTIVE_DEFAULT_CONCEPTS = tuple(
    (slot, concept) for slot, concept in enumerate(DEFAULT_CONCEPTS, start=1)
    if slot not in RETIRED_CONCEPT_SLOTS
)
