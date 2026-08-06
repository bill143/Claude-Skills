from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.api.projects import get_project_or_404
from app.db.session import get_db
from app.models.approval import ApprovalRequest
from app.models.change_order import ChangeOrder
from app.models.enums import ApprovalStatus, ChangeOrderStatus, ChangeOrderType, ForecastMethod
from app.models.user import User
from app.schemas.dashboard import ProjectKpis
from app.services import forecast_service

router = APIRouter(tags=["dashboard"])


@router.get("/projects/{project_id}/kpis", response_model=ProjectKpis)
def project_kpis(
    project_id: int,
    method: ForecastMethod = Query(default=ForecastMethod.REMAINING_BUDGET),
    percent_complete: float | None = Query(default=None, ge=0.0, le=1.0),
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    project = get_project_or_404(project_id, db)
    kpis = forecast_service.project_kpis(
        db, project, method=method, percent_complete=percent_complete
    )
    kpis["open_pcos"] = db.execute(
        select(func.count(ChangeOrder.id)).where(
            ChangeOrder.project_id == project_id,
            ChangeOrder.co_type == ChangeOrderType.PCO,
            ChangeOrder.status.in_(
                [ChangeOrderStatus.DRAFT, ChangeOrderStatus.PRICING, ChangeOrderStatus.SUBMITTED]
            ),
        )
    ).scalar_one()
    kpis["pending_approvals"] = db.execute(
        select(func.count(ApprovalRequest.id)).where(
            ApprovalRequest.status == ApprovalStatus.PENDING
        )
    ).scalar_one()
    return kpis
