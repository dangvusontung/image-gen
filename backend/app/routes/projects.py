from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session, selectinload

from app.builtin import is_builtin
from app.database import get_db
from app.models import SOURCE_KINDS, Asset, GenerationJob, JobStatus, MasterVersion, Preset, Project
from app.providers.base import CapabilityError
from app.providers.registry import ProviderRegistry, get_registry
from app.routes.assets import storage
from app.schemas import (AssetResponse, ProjectCreate, ProjectDetail, ProjectSummary, ProjectUpdate,
                         StepLeadUpdate, StepTemplateUpdate)

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
        workflow_mode=project.workflow_mode,
        step_leads=project.step_leads or {},
        step_templates=project.step_templates or {},
        preset_id=project.preset_id,
        created_at=project.created_at,
        updated_at=project.updated_at,
        assets=[AssetResponse.model_validate(a) for a in project.source_assets],
    )


@router.get("", response_model=list[ProjectSummary])
def list_projects(db: Session = Depends(get_db)):
    projects = (
        db.query(Project).options(selectinload(Project.source_assets)).order_by(Project.updated_at.desc()).all()
    )
    jobs = db.query(GenerationJob).order_by(GenerationJob.updated_at.desc()).all()
    by_project = {}
    for job in jobs:
        by_project.setdefault(job.project_id, []).append(job)
    thumbnails = {}
    for master in db.query(MasterVersion).filter(MasterVersion.id.in_([p.approved_master_id for p in projects if p.approved_master_id])):
        if master.job.output_asset_ids:
            thumbnails[master.project_id] = master.job.output_asset_ids[0]
    return [
        ProjectSummary(
            id=p.id,
            name=p.name,
            description=p.description,
            rights_confirmed=p.rights_confirmed,
            provider=p.provider,
            model=p.model,
            workflow_mode=p.workflow_mode,
            created_at=p.created_at,
            updated_at=p.updated_at,
            asset_count=len(p.source_assets),
            thumbnail_asset_id=thumbnails.get(p.id) or (p.source_assets[0].id if p.source_assets else None),
            completed_jobs=sum(j.status == JobStatus.SUCCEEDED for j in by_project.get(p.id, [])),
            active_jobs=sum(j.status in JobStatus.ACTIVE for j in by_project.get(p.id, [])),
            failed_jobs=sum(j.status == JobStatus.FAILED for j in by_project.get(p.id, [])),
            recent_activity=by_project[p.id][0].purpose if by_project.get(p.id) else None,
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


@router.put("/{project_id}/step-lead", response_model=ProjectDetail)
def set_step_lead(project_id: str, data: StepLeadUpdate, db: Session = Depends(get_db)):
    """Pin which reference leads one step, or clear it to go back to the automatic choice."""
    project = get_project_or_404(db, project_id)
    leads = dict(project.step_leads or {})
    if data.lead:
        leads[data.step] = data.lead
    else:
        leads.pop(data.step, None)
    project.step_leads = leads
    db.commit()
    db.refresh(project)
    return _detail(project)


@router.put("/{project_id}/step-template", response_model=ProjectDetail)
def set_step_template(project_id: str, data: StepTemplateUpdate, db: Session = Depends(get_db)):
    """Pin the template image that steers one step's art direction, or clear it."""
    project = get_project_or_404(db, project_id)
    if data.asset_id and data.asset_id != "none" and not is_builtin(data.asset_id):
        asset = db.get(Asset, data.asset_id)
        if asset is None or asset.project_id != project_id or asset.kind not in SOURCE_KINDS:
            raise HTTPException(404, detail={"code": "template_not_found", "message": "Không tìm thấy ảnh mẫu"})
    templates = dict(project.step_templates or {})
    if data.asset_id:
        templates[data.step] = data.asset_id
    else:
        templates.pop(data.step, None)
    project.step_templates = templates
    db.commit()
    db.refresh(project)
    return _detail(project)


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

    if changes.get("preset_id") and db.get(Preset, changes["preset_id"]) is None:
        raise HTTPException(status_code=404, detail={"code": "preset_not_found", "message": "Không tìm thấy bộ cấu hình"})

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
