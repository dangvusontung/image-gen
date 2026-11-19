"""Database owns catalog visibility; JSON only seeds previously unseen slots."""
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.dialects.postgresql import insert as postgres_insert

from app.concept_defaults import get_catalog
from app.models import ConceptCatalogState


def database_catalog(db):
    catalog = get_catalog()
    existing = {row.slot for row in db.query(ConceptCatalogState).all()}
    missing = [dict(slot=row.slot, archived=row.slot in catalog.retired_slots,
                    replacement_slot=catalog.retired_slots.get(row.slot))
               for row in catalog.concepts if row.slot not in existing]
    if missing:
        insert = sqlite_insert if db.get_bind().dialect.name == "sqlite" else postgres_insert
        db.execute(insert(ConceptCatalogState).values(missing).on_conflict_do_nothing(index_elements=["slot"]))
        db.commit()
    states = db.query(ConceptCatalogState).filter(ConceptCatalogState.archived.is_(True)).all()
    # Archived entries without a replacement are still excluded from defaults.
    return catalog.model_copy(update={"retired_slots": {row.slot: row.replacement_slot for row in states}})
