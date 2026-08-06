from decimal import Decimal

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_roles
from app.api.projects import get_project_or_404
from app.db.session import get_db
from app.models.budget import BudgetLine
from app.models.change_order import ChangeOrder
from app.models.enums import (
    ApprovalEntityType,
    ChangeOrderStatus,
    ChangeOrderType,
    PurchaseOrderStatus,
    UserRole,
)
from app.models.purchase_order import PurchaseOrder, PurchaseOrderLine
from app.models.user import User
from app.models.vendor import Vendor
from app.schemas.approval import ApprovalRequestOut
from app.schemas.purchase_order import (
    POSubmitResult,
    POTransitionIn,
    PurchaseOrderCreate,
    PurchaseOrderOut,
)
from app.services import (
    approval_service,
    audit_service,
    idempotency_service,
    numbering_service,
    workflow_service,
)

router = APIRouter(tags=["purchase-orders"])


def get_po_or_404(po_id: int, db: Session) -> PurchaseOrder:
    po = db.get(PurchaseOrder, po_id)
    if po is None:
        raise HTTPException(status_code=404, detail="Purchase order not found")
    return po


@router.post("/projects/{project_id}/purchase-orders", response_model=PurchaseOrderOut, status_code=201)
def create_purchase_order(
    project_id: int,
    body: PurchaseOrderCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(UserRole.PROJECT_MANAGER)),
):
    project = get_project_or_404(project_id, db)
    vendor_id = body.vendor_id
    source_co = None
    if body.source_change_order_id is not None:
        source_co = db.get(ChangeOrder, body.source_change_order_id)
        if source_co is None or source_co.project_id != project.id:
            raise HTTPException(status_code=422, detail="Source change order not found on this project")
        if source_co.co_type != ChangeOrderType.SCO:
            raise HTTPException(status_code=422, detail="POs can only be sourced from an SCO")
        if source_co.status != ChangeOrderStatus.APPROVED:
            raise HTTPException(status_code=422, detail="Source SCO must be APPROVED")
        vendor_id = source_co.vendor_id or vendor_id

    if db.get(Vendor, vendor_id) is None:
        raise HTTPException(status_code=404, detail="Vendor not found")
    if source_co is None and not body.lines:
        raise HTTPException(status_code=422, detail="Purchase order requires at least one line")

    po = PurchaseOrder(
        project_id=project.id,
        number=numbering_service.next_purchase_order_number(db, project.id),
        vendor_id=vendor_id,
        source_change_order_id=source_co.id if source_co else None,
        issued_date=body.issued_date,
        notes=body.notes,
        created_by_id=user.id,
    )
    db.add(po)
    db.flush()

    if source_co is not None:
        for line in source_co.lines:
            db.add(PurchaseOrderLine(
                purchase_order_id=po.id,
                budget_line_id=line.budget_line_id,
                description=line.description,
                quantity=line.quantity,
                unit_cost=line.unit_cost,
                amount=line.amount,
            ))
    else:
        for line in body.lines:
            budget_line = db.get(BudgetLine, line.budget_line_id)
            if budget_line is None or budget_line.project_id != project.id:
                raise HTTPException(
                    status_code=422,
                    detail=f"Budget line {line.budget_line_id} does not belong to project {project.id}",
                )
            quantity = line.quantity
            unit_cost = line.unit_cost
            db.add(PurchaseOrderLine(
                purchase_order_id=po.id,
                budget_line_id=line.budget_line_id,
                description=line.description,
                quantity=quantity,
                unit_cost=unit_cost,
                amount=(quantity * unit_cost).quantize(Decimal("0.01")),
            ))
    db.flush()
    audit_service.record(
        db, actor=user, entity_type="PURCHASE_ORDER", entity_id=po.id,
        action="created",
        payload={"number": po.number, "vendor_id": vendor_id,
                 "source_sco": source_co.number if source_co else None},
    )
    db.commit()
    db.refresh(po)
    return po


@router.get("/projects/{project_id}/purchase-orders", response_model=list[PurchaseOrderOut])
def list_purchase_orders(
    project_id: int,
    status: PurchaseOrderStatus | None = Query(default=None),
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    get_project_or_404(project_id, db)
    query = select(PurchaseOrder).where(PurchaseOrder.project_id == project_id)
    if status is not None:
        query = query.where(PurchaseOrder.status == status)
    return db.execute(query.order_by(PurchaseOrder.id.desc())).scalars().all()


@router.get("/purchase-orders/{po_id}", response_model=PurchaseOrderOut)
def get_purchase_order(po_id: int, db: Session = Depends(get_db), _user: User = Depends(get_current_user)):
    return get_po_or_404(po_id, db)


@router.get("/purchase-orders/{po_id}/approvals", response_model=list[ApprovalRequestOut])
def get_purchase_order_approvals(
    po_id: int, db: Session = Depends(get_db), _user: User = Depends(get_current_user)
):
    get_po_or_404(po_id, db)
    return approval_service.requests_for_entity(db, ApprovalEntityType.PURCHASE_ORDER, po_id)


@router.post("/purchase-orders/{po_id}/submit", response_model=POSubmitResult)
def submit_purchase_order(
    po_id: int,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(UserRole.PROJECT_MANAGER)),
):
    po = get_po_or_404(po_id, db)
    return idempotency_service.run_idempotent(
        db,
        key=idempotency_key,
        user=user,
        endpoint=f"purchase_orders.submit.{po_id}",
        payload={"po_id": po_id},
        fn=lambda: workflow_service.submit_purchase_order(db, po, user),
    )


@router.post("/purchase-orders/{po_id}/transition", response_model=PurchaseOrderOut)
def transition_purchase_order(
    po_id: int,
    body: POTransitionIn,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(UserRole.PROJECT_MANAGER)),
):
    po = get_po_or_404(po_id, db)
    return workflow_service.transition_purchase_order(db, po, body.action, user)
