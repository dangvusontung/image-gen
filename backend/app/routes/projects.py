from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session, selectinload

from app.database import get_db
from app.models import Project
from app.routes.assets import storage
from app.schemas import ProjectCreate, ProjectDetail, ProjectSummary, ProjectUpdate

router = APIRouter(prefix="/api/projects", tags=["projects"])


def get_project_or_404(db: Session, project_id: str) -> Project:
    project = db.get(Project, project_id)
    if not project:
        raise HTTPException(status_code=404, detail={"code": "project_not_found", "message": "Không tìm thấy dự án"})
    return project


@router.get("", response_model=list[ProjectSummary])
def list_projects(db: Session = Depends(get_db)):
    projects = (
        db.query(Project).options(selectinload(Project.assets)).order_by(Project.updated_at.desc()).all()
    )
    return [
        ProjectSummary(
            id=p.id,
            name=p.name,
            description=p.description,
            rights_confirmed=p.rights_confirmed,
            created_at=p.created_at,
            updated_at=p.updated_at,
            asset_count=len(p.assets),
            thumbnail_asset_id=p.assets[0].id if p.assets else None,
        )
        for p in projects
    ]


@router.post("", response_model=ProjectDetail, status_code=201)
def create_project(data: ProjectCreate, db: Session = Depends(get_db)):
    project = Project(name=data.name.strip(), description=data.description)
    db.add(project)
    db.commit()
    db.refresh(project)
    return project


@router.get("/{project_id}", response_model=ProjectDetail)
def get_project(project_id: str, db: Session = Depends(get_db)):
    return get_project_or_404(db, project_id)


@router.patch("/{project_id}", response_model=ProjectDetail)
def update_project(project_id: str, data: ProjectUpdate, db: Session = Depends(get_db)):
    project = get_project_or_404(db, project_id)
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(project, field, value.strip() if field == "name" else value)
    db.commit()
    db.refresh(project)
    return project


@router.delete("/{project_id}", status_code=204)
def delete_project(project_id: str, db: Session = Depends(get_db)):
    project = get_project_or_404(db, project_id)
    db.delete(project)
    db.commit()
    storage.delete_project_dir(project_id)
