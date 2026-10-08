"""Versioned prompt templates (files) with append-only global/per-project overrides (DB)."""

import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from sqlalchemy.orm import Session

from app.models import PromptTemplate

TEMPLATE_DIR = Path(__file__).parent / "templates"
_PLACEHOLDER = re.compile(r"\{([a-z_]+)\}")
MAX_TEMPLATE_CHARS = 8000


@dataclass(frozen=True)
class TemplateSpec:
    name: str
    version: int
    variables: tuple[str, ...]
    label: str

    @property
    def path(self) -> Path:
        return TEMPLATE_DIR / f"{self.name}.v{self.version}.txt"


SPECS = {
    s.name: s
    for s in (
        TemplateSpec("master", 1, (), "Nhân vật gốc"),
        TemplateSpec("turnaround", 1, ("angle",), "Turnaround"),
        TemplateSpec("concept", 1, ("mood", "camera", "prior_briefs", "brief"), "Concept"),
        TemplateSpec("enhance", 1, (), "Nâng cấp"),
    )
}


class TemplateError(ValueError):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code, self.message = code, message


def get_spec(name: str) -> TemplateSpec:
    try:
        return SPECS[name]
    except KeyError:
        raise TemplateError("unknown_template", f"Không có prompt template '{name}'") from None


@lru_cache(maxsize=None)
def default_body(name: str) -> str:
    return get_spec(name).path.read_text(encoding="utf-8").strip()


def validate_body(name: str, body: str) -> str:
    body = body.strip()
    if not body:
        raise TemplateError("empty_template", "Prompt không được để trống")
    if len(body) > MAX_TEMPLATE_CHARS:
        raise TemplateError("template_too_long", f"Prompt tối đa {MAX_TEMPLATE_CHARS} ký tự")
    allowed = set(get_spec(name).variables)
    unknown = sorted(set(_PLACEHOLDER.findall(body)) - allowed)
    if unknown:
        hint = ", ".join("{" + v + "}" for v in sorted(allowed)) or "không có"
        raise TemplateError("unknown_placeholder", f"Biến không hợp lệ: {', '.join(unknown)} (được dùng: {hint})")
    return body


def _latest(db: Session, name: str, project_id: str | None) -> PromptTemplate | None:
    q = db.query(PromptTemplate).filter(PromptTemplate.name == name)
    q = q.filter(PromptTemplate.project_id == project_id) if project_id else q.filter(PromptTemplate.project_id.is_(None))
    return q.order_by(PromptTemplate.revision.desc()).first()


@dataclass
class ResolvedTemplate:
    name: str
    body: str
    source: str  # "default" | "global" | "project"
    template_version: int
    revision: int | None


def resolve(db: Session, name: str, project_id: str | None = None) -> ResolvedTemplate:
    spec = get_spec(name)
    scopes = ([("project", project_id)] if project_id else []) + [("global", None)]
    for source, scope_id in scopes:
        row = _latest(db, name, scope_id)
        if row is not None and row.body is not None:
            return ResolvedTemplate(name, row.body, source, spec.version, row.revision)
    return ResolvedTemplate(name, default_body(name), "default", spec.version, None)


def save_override(db: Session, name: str, body: str | None, project_id: str | None) -> PromptTemplate:
    """Append a new revision; body=None records a reset to the inherited template."""
    if body is not None:
        body = validate_body(name, body)
    latest = _latest(db, name, project_id)
    row = PromptTemplate(
        name=name,
        project_id=project_id,
        body=body,
        template_version=get_spec(name).version,
        revision=(latest.revision + 1) if latest else 1,
    )
    db.add(row)
    return row


def render(body: str, **values: str) -> str:
    """Substitute only known {placeholders}; other braces in user text are left untouched."""
    return _PLACEHOLDER.sub(lambda m: str(values[m.group(1)]) if m.group(1) in values else m.group(0), body)
