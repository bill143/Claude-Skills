from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_roles
from app.db.session import get_db
from app.models.approval import ApprovalRequest, ApprovalRule
from app.models.enums import UserRole
from app.models.user import User
from app.schemas.approval import (
    ApprovalRequestOut,
    ApprovalRuleCreate,
    ApprovalRuleOut,
    DecisionIn,
    DecisionOut,
)
from app.services import approval_service

router = APIRouter(prefix="/approvals", tags=["approvals"])


@router.get("/pending", response_model=list[ApprovalRequestOut])
def my_pending_approvals(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return approval_service.pending_for_user(db, user)


@router.post("/{request_id}/decide", response_model=DecisionOut)
def decide(
    request_id: int,
    body: DecisionIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    request = db.get(ApprovalRequest, request_id)
    if request is None:
        raise HTTPException(status_code=404, detail="Approval request not found")
    return approval_service.decide(
        db, request=request, approver=user, approve=body.approve, comment=body.comment
    )


@router.get("/rules", response_model=list[ApprovalRuleOut])
def list_rules(db: Session = Depends(get_db), _user: User = Depends(get_current_user)):
    return db.execute(
        select(ApprovalRule).order_by(ApprovalRule.entity_type, ApprovalRule.sequence)
    ).scalars().all()


@router.post("/rules", response_model=ApprovalRuleOut, status_code=201)
def create_rule(
    body: ApprovalRuleCreate,
    db: Session = Depends(get_db),
    _admin: User = Depends(require_roles(UserRole.ADMIN)),
):
    from decimal import Decimal

    rule = ApprovalRule(
        entity_type=body.entity_type,
        role=body.role,
        threshold_amount=Decimal(str(body.threshold_amount)),
        sequence=body.sequence,
        description=body.description,
    )
    db.add(rule)
    db.commit()
    db.refresh(rule)
    return rule
