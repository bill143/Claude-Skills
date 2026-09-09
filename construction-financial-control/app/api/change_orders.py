from decimal import Decimal

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_roles
from app.api.projects import get_project_or_404
from app.db.session import get_db
from app.models.budget import BudgetLine
from app.models.change_order import ChangeOrder, ChangeOrderLine
from app.models.enums import ApprovalEntityType, ChangeOrderStatus, ChangeOrderType, UserRole
from app.models.user import User
from app.models.vendor import Vendor
from app.schemas.approval import ApprovalRequestOut
from app.schemas.change_order import (
    ChangeOrderCreate,
    ChangeOrderLineIn,
    ChangeOrderOut,
    ConvertIn,
    TransitionIn,
)
from app.services import (
    approval_service,
    audit_service,
    idempotency_service,
    numbering_service,
    workflow_service,
)

router = APIRouter(tags=["change-orders"])


def serialize_co(co: ChangeOrder) -> ChangeOrderOut:
    out = ChangeOrderOut.model_validate(co)
    out.allowed_actions = workflow_service.allowed_change_order_actions(co)
    return out


def get_co_or_404(co_id: int, db: Session) -> ChangeOrder:
    co = db.get(ChangeOrder, co_id)
    if co is None:
        raise HTTPException(status_code=404, detail="Change order not found")
    return co


def _validate_lines(db: Session, project_id: int, lines: list[ChangeOrderLineIn]) -> None:
    for line in lines:
        budget_line = db.get(BudgetLine, line.budget_line_id)
        if budget_line is None or budget_line.project_id != project_id:
            raise HTTPException(
                status_code=422,
                detail=f"Budget line {line.budget_line_id} does not belong to project {project_id}",
            )


@router.post("/projects/{project_id}/change-orders", response_model=ChangeOrderOut, status_code=201)
def create_change_order(
    project_id: int,
    body: ChangeOrderCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(UserRole.PROJECT_MANAGER)),
):
    project = get_project_or_404(project_id, db)
    if body.co_type == ChangeOrderType.SCO:
        if body.vendor_id is None:
            raise HTTPException(status_code=422, detail="SCO requires vendor_id")
        if db.get(Vendor, body.vendor_id) is None:
            raise HTTPException(status_code=404, detail="Vendor not found")
    _validate_lines(db, project.id, body.lines)

    co = ChangeOrder(
        project_id=project.id,
        number=numbering_service.next_change_order_number(db, project.id, body.co_type),
        co_type=body.co_type,
        title=body.title,
        description=body.description,
        vendor_id=body.vendor_id if body.co_type == ChangeOrderType.SCO else None,
        schedule_impact_days=body.schedule_impact_days,
        created_by_id=user.id,
    )
    db.add(co)
    db.flush()
    for line in body.lines:
        quantity = line.quantity
        unit_cost = line.unit_cost
        db.add(ChangeOrderLine(
            change_order_id=co.id,
            budget_line_id=line.budget_line_id,
            description=line.description,
            quantity=quantity,
            unit_cost=unit_cost,
            amount=(quantity * unit_cost).quantize(Decimal("0.01")),
        ))
    db.flush()
    audit_service.record(
        db, actor=user, entity_type="CHANGE_ORDER", entity_id=co.id,
        action="created",
        payload={"number": co.number, "co_type": co.co_type.value, "title": co.title},
    )
    db.commit()
    db.refresh(co)
    return serialize_co(co)


@router.get("/projects/{project_id}/change-orders", response_model=list[ChangeOrderOut])
def list_change_orders(
    project_id: int,
    co_type: ChangeOrderType | None = Query(default=None),
    status: ChangeOrderStatus | None = Query(default=None),
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    get_project_or_404(project_id, db)
    query = select(ChangeOrder).where(ChangeOrder.project_id == project_id)
    if co_type is not None:
        query = query.where(ChangeOrder.co_type == co_type)
    if status is not None:
        query = query.where(ChangeOrder.status == status)
    cos = db.execute(query.order_by(ChangeOrder.id.desc())).scalars().all()
    return [serialize_co(co) for co in cos]


@router.get("/change-orders/{co_id}", response_model=ChangeOrderOut)
def get_change_order(co_id: int, db: Session = Depends(get_db), _user: User = Depends(get_current_user)):
    return serialize_co(get_co_or_404(co_id, db))


@router.get("/change-orders/{co_id}/approvals", response_model=list[ApprovalRequestOut])
def get_change_order_approvals(
    co_id: int, db: Session = Depends(get_db), _user: User = Depends(get_current_user)
):
    get_co_or_404(co_id, db)
    return approval_service.requests_for_entity(db, ApprovalEntityType.CHANGE_ORDER, co_id)


@router.post("/change-orders/{co_id}/transition", response_model=ChangeOrderOut)
def transition_change_order(
    co_id: int,
    body: TransitionIn,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(UserRole.PROJECT_MANAGER)),
):
    co = get_co_or_404(co_id, db)
    return idempotency_service.run_idempotent(
        db,
        key=idempotency_key,
        user=user,
        endpoint=f"change_orders.transition.{co_id}",
        payload=body,
        fn=lambda: serialize_co(workflow_service.transition_change_order(db, co, body.action, user)),
    )


@router.post("/change-orders/{co_id}/convert", response_model=list[ChangeOrderOut])
def convert_pco(
    co_id: int,
    body: ConvertIn,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(UserRole.PROJECT_MANAGER)),
):
    pco = get_co_or_404(co_id, db)

    def _convert():
        created = workflow_service.convert_pco(
            db,
            pco,
            targets=body.targets,
            actor=user,
            vendor_id=body.vendor_id,
            oco_markup_pct=body.oco_markup_pct,
        )
        return [serialize_co(doc) for doc in created]

    return idempotency_service.run_idempotent(
        db,
        key=idempotency_key,
        user=user,
        endpoint=f"change_orders.convert.{co_id}",
        payload=body,
        fn=_convert,
    )
