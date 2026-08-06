"""Budget, commitment, and forecast (EAC/ETC) computations.

Design sources:
- ERPNext Budget doctype + Budget Variance report: budget vs committed vs
  actual per cost dimension, derived (not denormalized) totals.
- OpenProject budgets module: planned vs actual rollup per container.
- Standard EVM formulas for the CPI method (PMBOK): EAC = BAC / CPI.

Cost model per budget line:
  current_budget = original_budget + approved OCO line amounts
  committed      = approved/closed PO lines + approved SCO lines not yet
                   superseded by a PO sourced from that SCO (no double count)
  actual         = sum of dated cost entries
  EAC (REMAINING_BUDGET) = max(committed, actual) + max(current_budget - committed, 0)
  EAC (CPI)              = actual + (current_budget - EV) / CPI, EV = pct_complete * current_budget
  ETC = EAC - actual ;  VAC = current_budget - EAC
"""
from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.budget import BudgetLine, CostEntry, ForecastSnapshot
from app.models.change_order import ChangeOrder, ChangeOrderLine
from app.models.enums import ChangeOrderStatus, ChangeOrderType, ForecastMethod, PurchaseOrderStatus
from app.models.project import Project
from app.models.purchase_order import PurchaseOrder, PurchaseOrderLine

ZERO = Decimal("0")
CENT = Decimal("0.01")
COMMITTED_PO_STATUSES = (PurchaseOrderStatus.APPROVED, PurchaseOrderStatus.CLOSED)


def _dec(value) -> Decimal:
    return Decimal(str(value)) if value is not None else ZERO


def _check_invariants(*, current_budget: Decimal, actual: Decimal, etc: Decimal, eac: Decimal,
                      vac: Decimal) -> None:
    """Financial identities that must hold for every forecast we emit."""
    if eac != (actual + etc).quantize(CENT):
        raise ValueError(f"Forecast invariant violated: EAC {eac} != actual {actual} + ETC {etc}")
    if vac != (current_budget - eac).quantize(CENT):
        raise ValueError(f"Forecast invariant violated: VAC {vac} != budget {current_budget} - EAC {eac}")


def approved_oco_changes(db: Session, budget_line_id: int) -> Decimal:
    total = db.execute(
        select(func.coalesce(func.sum(ChangeOrderLine.amount), 0))
        .join(ChangeOrder, ChangeOrderLine.change_order_id == ChangeOrder.id)
        .where(
            ChangeOrderLine.budget_line_id == budget_line_id,
            ChangeOrder.co_type == ChangeOrderType.OCO,
            ChangeOrder.status == ChangeOrderStatus.APPROVED,
        )
    ).scalar_one()
    return _dec(total)


def _sco_superseded_by_po(db: Session, sco_id: int) -> bool:
    exists = db.execute(
        select(PurchaseOrder.id).where(
            PurchaseOrder.source_change_order_id == sco_id,
            PurchaseOrder.status.in_(COMMITTED_PO_STATUSES),
        ).limit(1)
    ).scalar_one_or_none()
    return exists is not None


def committed_cost(db: Session, budget_line_id: int) -> Decimal:
    po_total = db.execute(
        select(func.coalesce(func.sum(PurchaseOrderLine.amount), 0))
        .join(PurchaseOrder, PurchaseOrderLine.purchase_order_id == PurchaseOrder.id)
        .where(
            PurchaseOrderLine.budget_line_id == budget_line_id,
            PurchaseOrder.status.in_(COMMITTED_PO_STATUSES),
        )
    ).scalar_one()

    sco_rows = db.execute(
        select(ChangeOrder.id, func.coalesce(func.sum(ChangeOrderLine.amount), 0))
        .join(ChangeOrderLine, ChangeOrderLine.change_order_id == ChangeOrder.id)
        .where(
            ChangeOrderLine.budget_line_id == budget_line_id,
            ChangeOrder.co_type == ChangeOrderType.SCO,
            ChangeOrder.status == ChangeOrderStatus.APPROVED,
        )
        .group_by(ChangeOrder.id)
    ).all()
    sco_total = sum(
        (_dec(amount) for sco_id, amount in sco_rows if not _sco_superseded_by_po(db, sco_id)), ZERO
    )
    return _dec(po_total) + sco_total


def actual_cost(db: Session, budget_line_id: int) -> Decimal:
    total = db.execute(
        select(func.coalesce(func.sum(CostEntry.amount), 0)).where(
            CostEntry.budget_line_id == budget_line_id
        )
    ).scalar_one()
    return _dec(total)


def line_metrics(
    db: Session,
    line: BudgetLine,
    method: ForecastMethod = ForecastMethod.REMAINING_BUDGET,
    percent_complete: float | None = None,
) -> dict:
    """Full derived cost picture for one budget line."""
    original = _dec(line.original_budget)
    changes = approved_oco_changes(db, line.id)
    current_budget = original + changes
    committed = committed_cost(db, line.id)
    actual = actual_cost(db, line.id)

    etc, eac, used_method = compute_etc_eac(
        current_budget=current_budget,
        committed=committed,
        actual=actual,
        method=method,
        percent_complete=percent_complete,
    )
    vac = (current_budget - eac).quantize(CENT)
    _check_invariants(current_budget=current_budget, actual=actual, etc=etc, eac=eac, vac=vac)
    # All arithmetic above is Decimal; float() below is a serialization-only
    # conversion of cent-quantized values (exact in IEEE-754 for our 16,2 range).
    return {
        "id": line.id,
        "cost_code": line.cost_code,
        "description": line.description,
        "category": line.category.value,
        "original_budget": float(original),
        "approved_changes": float(changes),
        "current_budget": float(current_budget),
        "committed": float(committed),
        "actual": float(actual),
        "etc": float(etc),
        "eac": float(eac),
        "vac": float(vac),
        "method": used_method.value,
    }


def compute_etc_eac(
    *,
    current_budget: Decimal,
    committed: Decimal,
    actual: Decimal,
    method: ForecastMethod,
    percent_complete: float | None = None,
) -> tuple[Decimal, Decimal, ForecastMethod]:
    """Return (ETC, EAC, method_actually_used).

    CPI falls back to REMAINING_BUDGET when it is undefined (no actuals or
    zero percent complete), so callers always get a finite forecast.
    """
    if method == ForecastMethod.CPI and percent_complete and actual > ZERO:
        pct = Decimal(str(min(max(percent_complete, 0.0), 1.0)))
        earned_value = current_budget * pct
        if earned_value > ZERO:
            cpi = earned_value / actual
            eac = (actual + (current_budget - earned_value) / cpi).quantize(CENT)
            return (eac - actual).quantize(CENT), eac, ForecastMethod.CPI

    # REMAINING_BUDGET: you will spend at least what you have committed (or
    # already spent, if overrun), plus every dollar of budget not yet bought out.
    uncommitted = current_budget - committed
    if uncommitted < ZERO:
        uncommitted = ZERO
    eac = (max(committed, actual) + uncommitted).quantize(CENT)
    return (eac - actual).quantize(CENT), eac, ForecastMethod.REMAINING_BUDGET


def project_forecast(
    db: Session,
    project: Project,
    method: ForecastMethod = ForecastMethod.REMAINING_BUDGET,
    percent_complete: float | None = None,
) -> dict:
    lines = [
        line_metrics(db, bl, method=method, percent_complete=percent_complete)
        for bl in project.budget_lines
    ]
    totals = {
        key: round(sum(row[key] for row in lines), 2)
        for key in ("original_budget", "approved_changes", "current_budget", "committed",
                    "actual", "etc", "eac", "vac")
    }
    return {"project_id": project.id, "method": method.value, "lines": lines, "totals": totals}


def approved_oco_total(db: Session, project_id: int) -> Decimal:
    rows = db.execute(
        select(func.coalesce(func.sum(ChangeOrderLine.amount), 0))
        .join(ChangeOrder, ChangeOrderLine.change_order_id == ChangeOrder.id)
        .where(
            ChangeOrder.project_id == project_id,
            ChangeOrder.co_type == ChangeOrderType.OCO,
            ChangeOrder.status == ChangeOrderStatus.APPROVED,
        )
    ).scalar_one()
    return _dec(rows)


def burn_rate_30d(db: Session, project_id: int, as_of: date | None = None) -> Decimal:
    """Actual cost posted in the trailing 30 days across the project."""
    as_of = as_of or date.today()
    window_start = as_of - timedelta(days=30)
    total = db.execute(
        select(func.coalesce(func.sum(CostEntry.amount), 0))
        .join(BudgetLine, CostEntry.budget_line_id == BudgetLine.id)
        .where(
            BudgetLine.project_id == project_id,
            CostEntry.entry_date > window_start,
            CostEntry.entry_date <= as_of,
        )
    ).scalar_one()
    return _dec(total)


def project_kpis(
    db: Session,
    project: Project,
    method: ForecastMethod = ForecastMethod.REMAINING_BUDGET,
    percent_complete: float | None = None,
) -> dict:
    forecast = project_forecast(db, project, method=method, percent_complete=percent_complete)
    totals = forecast["totals"]
    contract_value = float(_dec(project.original_contract_value) + approved_oco_total(db, project.id))
    eac = totals["eac"]
    pct_complete = round(totals["actual"] / eac, 4) if eac else 0.0
    return {
        "project_id": project.id,
        "project_code": project.code,
        "contract_value": contract_value,
        "original_budget": totals["original_budget"],
        "approved_changes": totals["approved_changes"],
        "current_budget": totals["current_budget"],
        "committed": totals["committed"],
        "actual_to_date": totals["actual"],
        "etc": totals["etc"],
        "eac": totals["eac"],
        "vac": totals["vac"],
        "projected_margin": round(contract_value - eac, 2),
        "burn_rate_30d": float(burn_rate_30d(db, project.id)),
        "percent_complete": pct_complete,
        "method": forecast["method"],
    }


def create_snapshot(
    db: Session,
    project: Project,
    *,
    method: ForecastMethod = ForecastMethod.REMAINING_BUDGET,
    percent_complete: float | None = None,
    created_by_id: int | None = None,
) -> ForecastSnapshot:
    forecast = project_forecast(db, project, method=method, percent_complete=percent_complete)
    totals = forecast["totals"]
    snapshot = ForecastSnapshot(
        project_id=project.id,
        as_of=date.today(),
        method=method,
        total_current_budget=_dec(totals["current_budget"]),
        total_committed=_dec(totals["committed"]),
        total_actual=_dec(totals["actual"]),
        total_etc=_dec(totals["etc"]),
        total_eac=_dec(totals["eac"]),
        total_vac=_dec(totals["vac"]),
        created_by_id=created_by_id,
    )
    db.add(snapshot)
    db.flush()
    return snapshot
