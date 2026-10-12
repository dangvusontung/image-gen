"""Attach manual job retries to new domain versions, leaving prior history intact."""
from sqlalchemy import func

from app.models import Concept, EnhancementVersion, MasterVersion, TurnaroundVersion, TurnaroundView


def attach_retry(db, old, new):
    db.flush()
    master = db.query(MasterVersion).filter_by(job_id=old.id).first()
    if master:
        number = (db.query(func.max(MasterVersion.round)).filter_by(project_id=old.project_id).scalar() or 0) + 1
        db.add(MasterVersion(project_id=old.project_id, job_id=new.id, round=number, variant=1))
    concept = db.query(Concept).filter_by(job_id=old.id).first()
    if concept:
        number = (db.query(func.max(Concept.revision)).filter_by(project_id=old.project_id, run=concept.run, slot=concept.slot).scalar() or 0) + 1
        db.add(Concept(project_id=old.project_id, job_id=new.id, run=concept.run, slot=concept.slot,
                       revision=number, mood=concept.mood, camera=concept.camera, brief=concept.brief,
                       master_version_id=concept.master_version_id, turnaround_version_id=concept.turnaround_version_id))
    enhancement = db.query(EnhancementVersion).filter_by(job_id=old.id).first()
    if enhancement:
        number = (db.query(func.max(EnhancementVersion.number)).filter_by(concept_id=enhancement.concept_id).scalar() or 0) + 1
        db.add(EnhancementVersion(project_id=old.project_id, job_id=new.id, concept_id=enhancement.concept_id, number=number,
                                  master_version_id=enhancement.master_version_id, turnaround_version_id=enhancement.turnaround_version_id))
    view = db.query(TurnaroundView).filter_by(job_id=old.id, selected=True).order_by(TurnaroundView.created_at.desc()).first()
    if view:
        original = view.version
        number = (db.query(func.max(TurnaroundVersion.number)).filter_by(project_id=old.project_id).scalar() or 0) + 1
        version = TurnaroundVersion(project_id=old.project_id, master_version_id=original.master_version_id,
                                    forked_from_id=original.id, number=number)
        db.add(version)
        db.flush()
        for v in original.views:
            if v.selected:
                db.add(TurnaroundView(turnaround_version_id=version.id, angle=v.angle,
                                      job_id=new.id if v.job_id == old.id else v.job_id, selected=True))
