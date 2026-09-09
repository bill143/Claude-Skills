from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_roles
from app.api.projects import get_project_or_404
from app.db.session import get_db
from app.models.budget import BudgetLine, CostEntry, ForecastSnapshot
from app.models.change_order import ChangeOrder, ChangeOrderLine
from app.models.enums import ForecastMethod, UserRole
from app.models.purchase_order import PurchaseOrder, PurchaseOrderLine
from app.models.user import User
from app.schemas.budget import (
    BudgetLineCreate,
    BudgetLineOut,
    BudgetLinePatch,
    CostEntryCreate,
    CostEntryOut,
    ForecastSnapshotOut,
    ProjectForecastOut,
)
from app.services import audit_service, forecast_service, import_service, wbs_service
from app.services.forecast_service import normalize_code

router = APIRouter(tags=["budget"])


@router.post("/projects/{project_id}/budget-lines", response_model=BudgetLineOut, status_code=201)
def create_budget_line(
    project_id: int,
    body: BudgetLineCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(UserRole.PROJECT_MANAGER, UserRole.FINANCE)),
):
    project = get_project_or_404(project_id, db)
    cost_code = normalize_code(body.cost_code)
    exists = db.execute(
        select(BudgetLine).where(
            BudgetLine.project_id == project.id, BudgetLine.cost_code == cost_code
        )
    ).scalar_one_or_none()
    if exists:
        raise HTTPException(status_code=409, detail=f"Cost code {cost_code} already exists")
    line = BudgetLine(
        project_id=project.id,
        cost_code=cost_code,
        description=body.description or wbs_service.lookup_title(db, cost_code)
        or f"Cost code {cost_code}",
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


@router.get("/projects/{project_id}/wbs")
def get_project_wbs(
    project_id: int,
    method: ForecastMethod = Query(default=ForecastMethod.REMAINING_BUDGET),
    percent_complete: float | None = Query(default=None, ge=0.0, le=1.0),
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    """Division -> Section -> Line WBS tree with rollups at every level."""
    project = get_project_or_404(project_id, db)
    return wbs_service.project_wbs(db, project, method=method, percent_complete=percent_complete)


@router.post("/projects/{project_id}/budget-lines/import")
async def import_budget(
    project_id: int,
    file: UploadFile = File(...),
    mode: str = Query(default="preview", pattern="^(preview|commit)$"),
    on_duplicate: str = Query(default="skip", pattern="^(skip|update|error)$"),
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(UserRole.PROJECT_MANAGER, UserRole.FINANCE)),
):
    """Bulk-load budget lines from .xlsx/.csv. mode=preview validates only."""
    project = get_project_or_404(project_id, db)
    content = await file.read()
    if len(content) > 10 * 1024 * 1024:
        raise HTTPException(status_code=422, detail="File larger than 10 MB")
    if mode == "preview":
        return import_service.analyze(db, project, file.filename or "upload", content)
    return import_service.commit(db, project, file.filename or "upload", content,
                                 actor=user, on_duplicate=on_duplicate)


@router.patch("/budget-lines/{line_id}", response_model=BudgetLineOut)
def patch_budget_line(
    line_id: int,
    body: BudgetLinePatch,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(UserRole.PROJECT_MANAGER, UserRole.FINANCE)),
):
    """Edit description or the PM's manual cost-to-complete (ETC) override."""
    line = db.get(BudgetLine, line_id)
    if line is None:
        raise HTTPException(status_code=404, detail="Budget line not found")
    changes: dict = {}
    if body.description is not None:
        changes["description"] = {"from": line.description, "to": body.description}
        line.description = body.description
    if body.clear_manual_etc:
        changes["manual_etc"] = {"from": str(line.manual_etc), "to": None}
        line.manual_etc = None
    elif body.manual_etc is not None:
        changes["manual_etc"] = {"from": str(line.manual_etc), "to": str(body.manual_etc)}
        line.manual_etc = body.manual_etc
    if not changes:
        raise HTTPException(status_code=422, detail="Nothing to update")
    audit_service.record(
        db, actor=user, entity_type="BUDGET_LINE", entity_id=line.id,
        action="line_updated", payload=changes,
    )
    db.commit()
    db.refresh(line)
    return line


@router.get("/budget-lines/{line_id}/detail")
def budget_line_detail(
    line_id: int,
    method: ForecastMethod = Query(default=ForecastMethod.REMAINING_BUDGET),
    percent_complete: float | None = Query(default=None, ge=0.0, le=1.0),
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    """Drill-down: every document behind this line's numbers."""
    line = db.get(BudgetLine, line_id)
    if line is None:
        raise HTTPException(status_code=404, detail="Budget line not found")

    co_rows = db.execute(
        select(ChangeOrder, ChangeOrderLine)
        .join(ChangeOrderLine, ChangeOrderLine.change_order_id == ChangeOrder.id)
        .where(ChangeOrderLine.budget_line_id == line.id)
        .order_by(ChangeOrder.id)
    ).all()
    po_rows = db.execute(
        select(PurchaseOrder, PurchaseOrderLine)
        .join(PurchaseOrderLine, PurchaseOrderLine.purchase_order_id == PurchaseOrder.id)
        .where(PurchaseOrderLine.budget_line_id == line.id)
        .order_by(PurchaseOrder.id)
    ).all()
    costs = db.execute(
        select(CostEntry).where(CostEntry.budget_line_id == line.id)
        .order_by(CostEntry.entry_date)
    ).scalars().all()

    return {
        "metrics": forecast_service.line_metrics(db, line, method=method,
                                                 percent_complete=percent_complete),
        "change_orders": [
            {"id": co.id, "number": co.number, "co_type": co.co_type.value,
             "status": co.status.value, "title": co.title, "line_amount": float(col.amount),
             "line_description": col.description}
            for co, col in co_rows
        ],
        "purchase_orders": [
            {"id": po.id, "number": po.number, "status": po.status.value,
             "vendor_id": po.vendor_id, "line_amount": float(pol.amount),
             "line_description": pol.description}
            for po, pol in po_rows
        ],
        "cost_entries": [
            {"id": c.id, "entry_date": str(c.entry_date), "amount": float(c.amount),
             "description": c.description}
            for c in costs
        ],
    }


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
