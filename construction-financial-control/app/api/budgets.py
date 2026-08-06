from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_roles
from app.api.projects import get_project_or_404
from app.db.session import get_db
from app.models.budget import BudgetLine, CostEntry, ForecastSnapshot
from app.models.enums import ForecastMethod, UserRole
from app.models.user import User
from app.schemas.budget import (
    BudgetLineCreate,
    BudgetLineOut,
    CostEntryCreate,
    CostEntryOut,
    ForecastSnapshotOut,
    ProjectForecastOut,
)
from app.services import audit_service, forecast_service

router = APIRouter(tags=["budget"])


@router.post("/projects/{project_id}/budget-lines", response_model=BudgetLineOut, status_code=201)
def create_budget_line(
    project_id: int,
    body: BudgetLineCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(UserRole.PROJECT_MANAGER, UserRole.FINANCE)),
):
    project = get_project_or_404(project_id, db)
    exists = db.execute(
        select(BudgetLine).where(
            BudgetLine.project_id == project.id, BudgetLine.cost_code == body.cost_code
        )
    ).scalar_one_or_none()
    if exists:
        raise HTTPException(status_code=409, detail=f"Cost code {body.cost_code} already exists")
    line = BudgetLine(
        project_id=project.id,
        cost_code=body.cost_code,
        description=body.description,
        category=body.category,
        original_budget=body.original_budget,
    )
    db.add(line)
    db.flush()
    audit_service.record(
        db, actor=user, entity_type="BUDGET_LINE", entity_id=line.id,
        action="created",
        payload={"cost_code": line.cost_code, "original_budget": str(line.original_budget)},
    )
    db.commit()
    db.refresh(line)
    return line


@router.get("/projects/{project_id}/budget-lines", response_model=list[BudgetLineOut])
def list_budget_lines(
    project_id: int, db: Session = Depends(get_db), _user: User = Depends(get_current_user)
):
    get_project_or_404(project_id, db)
    return db.execute(
        select(BudgetLine).where(BudgetLine.project_id == project_id).order_by(BudgetLine.cost_code)
    ).scalars().all()


@router.post("/budget-lines/{line_id}/costs", response_model=CostEntryOut, status_code=201)
def post_cost_entry(
    line_id: int,
    body: CostEntryCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(UserRole.PROJECT_MANAGER, UserRole.FINANCE)),
):
    line = db.get(BudgetLine, line_id)
    if line is None:
        raise HTTPException(status_code=404, detail="Budget line not found")
    entry = CostEntry(
        budget_line_id=line.id,
        entry_date=body.entry_date,
        amount=body.amount,
        description=body.description,
        created_by_id=user.id,
    )
    db.add(entry)
    db.flush()
    audit_service.record(
        db, actor=user, entity_type="BUDGET_LINE", entity_id=line.id,
        action="cost_posted",
        payload={"amount": str(entry.amount), "entry_date": str(entry.entry_date),
                 "description": entry.description or ""},
    )
    db.commit()
    db.refresh(entry)
    return entry


@router.get("/projects/{project_id}/forecast", response_model=ProjectForecastOut)
def get_project_forecast(
    project_id: int,
    method: ForecastMethod = Query(default=ForecastMethod.REMAINING_BUDGET),
    percent_complete: float | None = Query(default=None, ge=0.0, le=1.0),
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    project = get_project_or_404(project_id, db)
    return forecast_service.project_forecast(
        db, project, method=method, percent_complete=percent_complete
    )


@router.post("/projects/{project_id}/forecast/snapshot", response_model=ForecastSnapshotOut, status_code=201)
def create_forecast_snapshot(
    project_id: int,
    method: ForecastMethod = Query(default=ForecastMethod.REMAINING_BUDGET),
    percent_complete: float | None = Query(default=None, ge=0.0, le=1.0),
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(UserRole.PROJECT_MANAGER, UserRole.FINANCE, UserRole.EXECUTIVE)),
):
    project = get_project_or_404(project_id, db)
    snapshot = forecast_service.create_snapshot(
        db, project, method=method, percent_complete=percent_complete, created_by_id=user.id
    )
    audit_service.record(
        db, actor=user, entity_type="PROJECT", entity_id=project.id,
        action="forecast_snapshot",
        payload={"eac": str(snapshot.total_eac), "vac": str(snapshot.total_vac)},
    )
    db.commit()
    db.refresh(snapshot)
    return snapshot


@router.get("/projects/{project_id}/forecast/snapshots", response_model=list[ForecastSnapshotOut])
def list_forecast_snapshots(
    project_id: int, db: Session = Depends(get_db), _user: User = Depends(get_current_user)
):
    get_project_or_404(project_id, db)
    return db.execute(
        select(ForecastSnapshot)
        .where(ForecastSnapshot.project_id == project_id)
        .order_by(ForecastSnapshot.created_at.desc())
    ).scalars().all()
