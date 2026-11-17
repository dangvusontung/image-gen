"""Catalog bookmarks are shared across projects and clients of this local backend."""
import re

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.dialects.sqlite import insert
from sqlalchemy.orm import Session

from app.concept_defaults import get_catalog
from app.database import get_db
from app.models import ConceptBookmark, _now

router = APIRouter(prefix="/api/concept-bookmarks", tags=["concept bookmarks"])


class BookmarkUpdate(BaseModel):
    bookmarked: bool


def validate_key(key: str) -> None:
    if key.startswith("default:"):
        slot = key.removeprefix("default:")
        if slot.isdigit() and int(slot) in {c.slot for c in get_catalog().concepts}:
            return
    elif re.fullmatch(r"project:[a-f0-9-]{36}:run:[1-9]\d*:slot:[1-9]\d*", key) and len(key) <= 200:
        return
    raise HTTPException(422, detail="Invalid concept bookmark key")


@router.get("")
def list_bookmarks(db: Session = Depends(get_db)):
    return {"keys": [row.key for row in db.query(ConceptBookmark).order_by(ConceptBookmark.key)]}


@router.put("/{key}")
def update_bookmark(key: str, data: BookmarkUpdate, db: Session = Depends(get_db)):
    validate_key(key)
    if data.bookmarked:
        db.execute(insert(ConceptBookmark).values(key=key, created_at=_now()).on_conflict_do_nothing(index_elements=["key"]))
    else:
        db.query(ConceptBookmark).filter_by(key=key).delete()
    db.commit()
    return {"key": key, "bookmarked": data.bookmarked}
