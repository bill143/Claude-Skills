"""Sequential per-project document numbering (PCO-0001, PO-0003, ...).

Pattern: ERPNext naming series, simplified to a count-based series scoped to
(project, prefix). Uniqueness is enforced by DB constraints on (project, number).
"""
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.change_order import ChangeOrder
from app.models.enums import ChangeOrderType
from app.models.purchase_order import PurchaseOrder


def next_change_order_number(db: Session, project_id: int, co_type: ChangeOrderType) -> str:
    count = db.execute(
        select(func.count(ChangeOrder.id)).where(
            ChangeOrder.project_id == project_id, ChangeOrder.co_type == co_type
        )
    ).scalar_one()
    return f"{co_type.value}-{count + 1:04d}"


def next_purchase_order_number(db: Session, project_id: int) -> str:
    count = db.execute(
        select(func.count(PurchaseOrder.id)).where(PurchaseOrder.project_id == project_id)
    ).scalar_one()
    return f"PO-{count + 1:04d}"
