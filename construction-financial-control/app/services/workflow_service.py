"""Document lifecycle state machine + PCO conversion + PO budget control.

Design sources:
- Frappe Workflow engine: explicit (state, action) -> state transition tables
  with role gating, instead of ad-hoc status writes.
- Tryton @Workflow.transition: every transition is a guarded function that is
  the ONLY way a status changes.
- ERPNext Budget doctype: STOP / WARN / IGNORE action when a purchase order
  would push commitments past budget.
- Odoo purchase double-validation + OCA purchase-workflow tiers: submitting a
  PO or CO for approval spawns the threshold-based chain.
"""
from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.change_order import ChangeOrder, ChangeOrderLine
from app.models.enums import (
    ApprovalEntityType,
    BudgetControlAction,
    ChangeOrderStatus,
    ChangeOrderType,
    PurchaseOrderStatus,
)
from app.models.project import Project
from app.models.purchase_order import PurchaseOrder
from app.models.user import User
from app.services import approval_service, audit_service, forecast_service, numbering_service

CO = ChangeOrderStatus
PO = PurchaseOrderStatus

# (co_type, current_status) -> {action: next_status}. "submit_for_approval" is
# special-cased below because it also builds the approval chain.
PCO_TRANSITIONS = {
    CO.DRAFT: {"send_to_pricing": CO.PRICING, "void": CO.VOID},
    CO.PRICING: {"submit": CO.SUBMITTED, "void": CO.VOID},
    CO.SUBMITTED: {"void": CO.VOID},  # conversion happens via convert_pco()
}
CONTRACT_CO_TRANSITIONS = {  # OCO and SCO
    CO.DRAFT: {"submit_for_approval": CO.PENDING_APPROVAL, "void": CO.VOID},
    CO.REJECTED: {"revise": CO.DRAFT},
}
PO_TRANSITIONS = {
    PO.DRAFT: {"submit_for_approval": PO.PENDING_APPROVAL, "cancel": PO.CANCELLED},
    PO.REJECTED: {"revise": PO.DRAFT, "cancel": PO.CANCELLED},
    PO.APPROVED: {"close": PO.CLOSED},
}


def allowed_change_order_actions(co: ChangeOrder) -> list[str]:
    table = PCO_TRANSITIONS if co.co_type == ChangeOrderType.PCO else CONTRACT_CO_TRANSITIONS
    actions = list(table.get(co.status, {}).keys())
    if co.co_type == ChangeOrderType.PCO and co.status == CO.SUBMITTED:
        actions.append("convert")
    return actions


def transition_change_order(db: Session, co: ChangeOrder, action: str, actor: User) -> ChangeOrder:
    table = PCO_TRANSITIONS if co.co_type == ChangeOrderType.PCO else CONTRACT_CO_TRANSITIONS
    valid = table.get(co.status, {})
    if action not in valid:
        raise HTTPException(
            status_code=422,
            detail=f"Action '{action}' not allowed for {co.co_type.value} in status "
                   f"{co.status.value}. Allowed: {sorted(valid)}",
        )

    if action == "submit_for_approval":
        if co.total_amount <= Decimal("0"):
            raise HTTPException(status_code=422, detail="Cannot submit a zero-amount change order")
        if co.co_type == ChangeOrderType.SCO and co.vendor_id is None:
            raise HTTPException(status_code=422, detail="SCO requires a vendor before submission")

    old_status = co.status
    co.status = valid[action]
    audit_service.record(
        db, actor=actor, entity_type="CHANGE_ORDER", entity_id=co.id,
        action=f"transition:{action}",
        payload={"from": old_status.value, "to": co.status.value, "co_type": co.co_type.value},
    )

    if action == "submit_for_approval":
        chain = approval_service.build_chain(
            db,
            entity_type=ApprovalEntityType.CHANGE_ORDER,
            entity_id=co.id,
            amount=co.total_amount,
            actor=actor,
        )
        if not chain:  # no matching rules -> auto-approve, but leave an audit trail
            co.status = CO.APPROVED
            audit_service.record(
                db, actor=actor, entity_type="CHANGE_ORDER", entity_id=co.id,
                action="auto_approved_no_rules", payload={"total_amount": str(co.total_amount)},
            )

    db.commit()
    db.refresh(co)
    return co


def convert_pco(
    db: Session,
    pco: ChangeOrder,
    *,
    targets: list[ChangeOrderType],
    actor: User,
    vendor_id: int | None = None,
    oco_markup_pct: float = 0.0,
) -> list[ChangeOrder]:
    """Turn a SUBMITTED PCO into draft OCO and/or SCO documents.

    SCO lines copy the PCO cost lines verbatim (the buyout side).
    OCO lines apply the optional markup (owner price = cost * (1 + markup)).
    """
    if pco.co_type != ChangeOrderType.PCO:
        raise HTTPException(status_code=422, detail="Only a PCO can be converted")
    if pco.status != CO.SUBMITTED:
        raise HTTPException(status_code=422, detail="PCO must be SUBMITTED before conversion")
    targets = list(dict.fromkeys(targets))
    if not targets or any(t == ChangeOrderType.PCO for t in targets):
        raise HTTPException(status_code=422, detail="Conversion targets must be OCO and/or SCO")
    if ChangeOrderType.SCO in targets and vendor_id is None:
        raise HTTPException(status_code=422, detail="vendor_id is required to create an SCO")
    if not pco.lines:
        raise HTTPException(status_code=422, detail="PCO has no lines to convert")

    created: list[ChangeOrder] = []
    markup = Decimal(str(1.0 + max(oco_markup_pct, 0.0)))
    for target in targets:
        doc = ChangeOrder(
            project_id=pco.project_id,
            number=numbering_service.next_change_order_number(db, pco.project_id, target),
            co_type=target,
            status=CO.DRAFT,
            title=pco.title,
            description=pco.description,
            vendor_id=vendor_id if target == ChangeOrderType.SCO else None,
            origin_pco_id=pco.id,
            schedule_impact_days=pco.schedule_impact_days,
            created_by_id=actor.id,
        )
        db.add(doc)
        db.flush()
        for line in pco.lines:
            amount = line.amount if target == ChangeOrderType.SCO else (
                (line.amount * markup).quantize(Decimal("0.01"))
            )
            db.add(ChangeOrderLine(
                change_order_id=doc.id,
                budget_line_id=line.budget_line_id,
                description=line.description,
                quantity=line.quantity,
                unit_cost=line.unit_cost,
                amount=amount,
            ))
        db.flush()
        audit_service.record(
            db, actor=actor, entity_type="CHANGE_ORDER", entity_id=doc.id,
            action="created_from_pco",
            payload={"origin_pco": pco.number, "co_type": target.value},
        )
        created.append(doc)

    old_status = pco.status
    pco.status = CO.CONVERTED
    audit_service.record(
        db, actor=actor, entity_type="CHANGE_ORDER", entity_id=pco.id,
        action="transition:convert",
        payload={"from": old_status.value, "to": pco.status.value,
                 "created": [d.number for d in created]},
    )
    db.commit()
    for doc in created:
        db.refresh(doc)
    return created


def check_po_budget(db: Session, po: PurchaseOrder) -> list[dict]:
    """ERPNext-style budget control: evaluate each PO line against remaining budget.

    Returns warnings; raises HTTP 422 when the project is set to STOP.
    """
    project = db.get(Project, po.project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    if project.budget_control == BudgetControlAction.IGNORE:
        return []

    tolerance = Decimal(str(1.0 + settings.BUDGET_TOLERANCE_PCT))
    warnings = []
    for line in po.lines:
        budget_line = line.budget_line
        current_budget = Decimal(str(budget_line.original_budget)) + forecast_service.approved_oco_changes(
            db, budget_line.id
        )
        committed = forecast_service.committed_cost(db, budget_line.id)
        projected = committed + Decimal(str(line.amount))
        if projected > current_budget * tolerance:
            warnings.append({
                "budget_line_id": budget_line.id,
                "cost_code": budget_line.cost_code,
                "current_budget": float(current_budget),
                "committed": float(committed),
                "projected_committed": float(projected),
                "overrun": float(projected - current_budget),
            })

    if warnings and project.budget_control == BudgetControlAction.STOP:
        raise HTTPException(
            status_code=422,
            detail={"message": "Budget exceeded and project budget control is STOP",
                    "violations": warnings},
        )
    return warnings


def submit_purchase_order(db: Session, po: PurchaseOrder, actor: User) -> dict:
    if po.status != PO.DRAFT:
        raise HTTPException(status_code=422, detail=f"PO in status {po.status.value} cannot be submitted")
    if po.total_amount <= Decimal("0"):
        raise HTTPException(status_code=422, detail="Cannot submit a zero-amount purchase order")

    warnings = check_po_budget(db, po)
    for warning in warnings:
        audit_service.record(
            db, actor=actor, entity_type="PURCHASE_ORDER", entity_id=po.id,
            action="budget_warning", payload=warning,
        )

    old_status = po.status
    po.status = PO.PENDING_APPROVAL
    audit_service.record(
        db, actor=actor, entity_type="PURCHASE_ORDER", entity_id=po.id,
        action="transition:submit_for_approval",
        payload={"from": old_status.value, "to": po.status.value, "total": str(po.total_amount)},
    )
    chain = approval_service.build_chain(
        db,
        entity_type=ApprovalEntityType.PURCHASE_ORDER,
        entity_id=po.id,
        amount=po.total_amount,
        actor=actor,
    )
    if not chain:
        po.status = PO.APPROVED
        audit_service.record(
            db, actor=actor, entity_type="PURCHASE_ORDER", entity_id=po.id,
            action="auto_approved_no_rules", payload={"total_amount": str(po.total_amount)},
        )
    db.commit()
    db.refresh(po)
    return {"status": po.status.value, "budget_warnings": warnings, "approval_steps": len(chain)}


def transition_purchase_order(db: Session, po: PurchaseOrder, action: str, actor: User) -> PurchaseOrder:
    if action == "submit_for_approval":
        submit_purchase_order(db, po, actor)
        return po
    valid = PO_TRANSITIONS.get(po.status, {})
    if action not in valid:
        raise HTTPException(
            status_code=422,
            detail=f"Action '{action}' not allowed for PO in status {po.status.value}. "
                   f"Allowed: {sorted(valid)}",
        )
    old_status = po.status
    po.status = valid[action]
    audit_service.record(
        db, actor=actor, entity_type="PURCHASE_ORDER", entity_id=po.id,
        action=f"transition:{action}",
        payload={"from": old_status.value, "to": po.status.value},
    )
    db.commit()
    db.refresh(po)
    return po
