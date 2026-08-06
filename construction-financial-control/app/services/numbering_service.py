"""Sequential per-project document numbering (PCO-0001, PO-0003, ...).

Pattern: ERPNext naming series, simplified to a count-based series scoped to
(project, prefix). The project row is taken as a row-level mutex so two
concurrent creations cannot read the same count; the unique constraint on
(project, number) is the second line of defense.
"""
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.session import locked_get
from app.models.change_order import ChangeOrder
from app.models.enums import ChangeOrderType
from app.models.project import Project
from app.models.purchase_order import PurchaseOrder


def _lock_project(db: Session, project_id: int) -> None:
    locked_get(db, Project, project_id)


def next_change_order_number(db: Session, project_id: int, co_type: ChangeOrderType) -> str:
    _lock_project(db, project_id)
    count = db.execute(
        select(func.count(ChangeOrder.id)).where(
            ChangeOrder.project_id == project_id, ChangeOrder.co_type == co_type
        )
    ).scalar_one()
    return f"{co_type.value}-{count + 1:04d}"


def next_purchase_order_number(db: Session, project_id: int) -> str:
    _lock_project(db, project_id)
    count = db.execute(
        select(func.count(PurchaseOrder.id)).where(PurchaseOrder.project_id == project_id)
    ).scalar_one()
    return f"PO-{count + 1:04d}"
