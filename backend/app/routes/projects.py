from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session, selectinload

from app.database import get_db
from app.models import Project
from app.providers.base import CapabilityError
from app.providers.registry import ProviderRegistry, get_registry
from app.routes.assets import storage
from app.schemas import AssetResponse, ProjectCreate, ProjectDetail, ProjectSummary, ProjectUpdate

router = APIRouter(prefix="/api/projects", tags=["projects"])


def get_project_or_404(db: Session, project_id: str) -> Project:
    project = db.get(Project, project_id)
    if not project:
        raise HTTPException(status_code=404, detail={"code": "project_not_found", "message": "Không tìm thấy dự án"})
    return project


def _detail(project: Project) -> ProjectDetail:
    return ProjectDetail(
        id=project.id,
        name=project.name,
        description=project.description,
        rights_confirmed=project.rights_confirmed,
        provider=project.provider,
        model=project.model,
        created_at=project.created_at,
        updated_at=project.updated_at,
        assets=[AssetResponse.model_validate(a) for a in project.source_assets],
    )


@router.get("", response_model=list[ProjectSummary])
def list_projects(db: Session = Depends(get_db)):
    projects = (
        db.query(Project).options(selectinload(Project.source_assets)).order_by(Project.updated_at.desc()).all()
    )
    return [
        ProjectSummary(
            id=p.id,
            name=p.name,
            description=p.description,
            rights_confirmed=p.rights_confirmed,
            provider=p.provider,
            model=p.model,
            created_at=p.created_at,
            updated_at=p.updated_at,
            asset_count=len(p.source_assets),
            thumbnail_asset_id=p.source_assets[0].id if p.source_assets else None,
        )
        for p in projects
    ]


@router.post("", response_model=ProjectDetail, status_code=201)
def create_project(data: ProjectCreate, db: Session = Depends(get_db)):
    project = Project(name=data.name.strip(), description=data.description)
    db.add(project)
    db.commit()
    db.refresh(project)
    return _detail(project)


@router.get("/{project_id}", response_model=ProjectDetail)
def get_project(project_id: str, db: Session = Depends(get_db)):
    return _detail(get_project_or_404(db, project_id))


@router.patch("/{project_id}", response_model=ProjectDetail)
def update_project(
    project_id: str,
    data: ProjectUpdate,
    db: Session = Depends(get_db),
    registry: ProviderRegistry = Depends(get_registry),
):
    project = get_project_or_404(db, project_id)
    changes = data.model_dump(exclude_unset=True)

    if "provider" in changes or "model" in changes:
        provider_name = changes.get("provider", project.provider)
        try:
            provider = registry.get(provider_name)
            if not provider.selectable:
                raise CapabilityError("provider_disabled", f"{provider.display_name} chỉ để tham khảo, không chọn được")
            # Switching provider without naming a model picks that provider's default.
            model_id = changes.get("model") or (
                project.model if provider_name == project.provider else provider.default_model().id
            )
            provider.get_model(model_id)
        except CapabilityError as exc:
            raise HTTPException(status_code=400, detail={"code": exc.code, "message": exc.message})
        changes["provider"], changes["model"] = provider_name, model_id

    for field, value in changes.items():
        setattr(project, field, value.strip() if field == "name" else value)
    db.commit()
    db.refresh(project)
    return _detail(project)


@router.delete("/{project_id}", status_code=204)
def delete_project(project_id: str, db: Session = Depends(get_db)):
    project = get_project_or_404(db, project_id)
    db.delete(project)
    db.commit()
    storage.delete_project_dir(project_id)
