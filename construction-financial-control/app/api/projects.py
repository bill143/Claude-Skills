from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_roles
from app.db.session import get_db
from app.models.enums import UserRole
from app.models.project import Project
from app.models.user import User
from app.schemas.project import ProjectCreate, ProjectOut
from app.services import audit_service

router = APIRouter(prefix="/projects", tags=["projects"])


def get_project_or_404(project_id: int, db: Session) -> Project:
    project = db.get(Project, project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    return project


@router.post("", response_model=ProjectOut, status_code=201)
def create_project(
    body: ProjectCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(UserRole.PROJECT_MANAGER, UserRole.EXECUTIVE)),
):
    exists = db.execute(select(Project).where(Project.code == body.code)).scalar_one_or_none()
    if exists:
        raise HTTPException(status_code=409, detail=f"Project code {body.code} already exists")
    project = Project(
        code=body.code,
        name=body.name,
        owner_name=body.owner_name,
        original_contract_value=body.original_contract_value,
        budget_control=body.budget_control,
        start_date=body.start_date,
        end_date=body.end_date,
    )
    db.add(project)
    db.flush()
    audit_service.record(
        db, actor=user, entity_type="PROJECT", entity_id=project.id,
        action="created", payload={"code": project.code, "name": project.name},
    )
    db.commit()
    db.refresh(project)
    return project


@router.get("", response_model=list[ProjectOut])
def list_projects(db: Session = Depends(get_db), _user: User = Depends(get_current_user)):
    return db.execute(select(Project).order_by(Project.code)).scalars().all()


@router.get("/{project_id}", response_model=ProjectOut)
def get_project(
    project_id: int, db: Session = Depends(get_db), _user: User = Depends(get_current_user)
):
    return get_project_or_404(project_id, db)
