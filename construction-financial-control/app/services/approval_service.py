"""Role + threshold approval engine.

Design sources:
- OCA base_tier_validation (used across OCA/purchase-workflow): ordered tiers
  of (role, condition) that must all sign off before a document validates.
- Dolibarr supplier orders: second-level approval above an amount threshold.
- Apache Fineract maker-checker: the submitter never self-approves silently;
  every decision is journaled.

Chain construction: for a document of amount X and entity type T, every
ApprovalRule of type T with threshold_amount <= X contributes one step,
ordered by rule sequence. Steps must be decided in order. Any rejection
rejects the document and auto-closes the remaining steps.
"""
from datetime import datetime, timezone
from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.approval import ApprovalRequest, ApprovalRule
from app.models.change_order import ChangeOrder
from app.models.enums import (
    ApprovalEntityType,
    ApprovalStatus,
    ChangeOrderStatus,
    PurchaseOrderStatus,
    UserRole,
)
from app.models.purchase_order import PurchaseOrder
from app.models.user import User
from app.services import audit_service


def build_chain(
    db: Session,
    *,
    entity_type: ApprovalEntityType,
    entity_id: int,
    amount: Decimal,
    actor: User,
) -> list[ApprovalRequest]:
    """Create the pending approval steps for a document. Empty list if no rule matches."""
    rules = db.execute(
        select(ApprovalRule)
        .where(ApprovalRule.entity_type == entity_type, ApprovalRule.threshold_amount <= amount)
        .order_by(ApprovalRule.sequence.asc())
    ).scalars().all()

    requests = []
    for rule in rules:
        request = ApprovalRequest(
            entity_type=entity_type,
            entity_id=entity_id,
            sequence=rule.sequence,
            required_role=rule.role,
            status=ApprovalStatus.PENDING,
        )
        db.add(request)
        requests.append(request)
    db.flush()
    audit_service.record(
        db,
        actor=actor,
        entity_type=entity_type.value,
        entity_id=entity_id,
        action="approval_chain_created",
        payload={"amount": str(amount), "steps": [
            {"sequence": r.sequence, "role": r.required_role.value} for r in requests
        ]},
    )
    return requests


def _load_entity(db: Session, entity_type: ApprovalEntityType, entity_id: int):
    model = ChangeOrder if entity_type == ApprovalEntityType.CHANGE_ORDER else PurchaseOrder
    entity = db.get(model, entity_id)
    if entity is None:
        raise HTTPException(status_code=404, detail=f"{entity_type.value} {entity_id} not found")
    return entity


def _finalize_approved(db: Session, entity_type: ApprovalEntityType, entity, actor: User) -> None:
    if entity_type == ApprovalEntityType.CHANGE_ORDER:
        entity.status = ChangeOrderStatus.APPROVED
        effect = "budget_revised" if entity.co_type.value == "OCO" else "commitment_posted"
    else:
        entity.status = PurchaseOrderStatus.APPROVED
        effect = "commitment_posted"
    audit_service.record(
        db, actor=actor, entity_type=entity_type.value, entity_id=entity.id,
        action="approved", payload={"total_amount": str(entity.total_amount), "effect": effect},
    )


def _finalize_rejected(db: Session, entity_type: ApprovalEntityType, entity, actor: User,
                       comment: str | None) -> None:
    if entity_type == ApprovalEntityType.CHANGE_ORDER:
        entity.status = ChangeOrderStatus.REJECTED
    else:
        entity.status = PurchaseOrderStatus.REJECTED
    audit_service.record(
        db, actor=actor, entity_type=entity_type.value, entity_id=entity.id,
        action="rejected", payload={"comment": comment or ""},
    )


def decide(db: Session, *, request: ApprovalRequest, approver: User,
           approve: bool, comment: str | None = None) -> dict:
    """Record one approval decision, enforcing sequence order and role."""
    if request.status != ApprovalStatus.PENDING:
        raise HTTPException(status_code=409, detail="Approval step already decided")
    if approver.role not in (request.required_role, UserRole.ADMIN):
        raise HTTPException(
            status_code=403,
            detail=f"Step requires role {request.required_role.value}",
        )
    earlier_pending = db.execute(
        select(ApprovalRequest).where(
            ApprovalRequest.entity_type == request.entity_type,
            ApprovalRequest.entity_id == request.entity_id,
            ApprovalRequest.status == ApprovalStatus.PENDING,
            ApprovalRequest.sequence < request.sequence,
        ).limit(1)
    ).scalar_one_or_none()
    if earlier_pending is not None:
        raise HTTPException(status_code=409, detail="Earlier approval steps are still pending")

    request.status = ApprovalStatus.APPROVED if approve else ApprovalStatus.REJECTED
    request.approver_id = approver.id
    request.comment = comment
    request.decided_at = datetime.now(timezone.utc)

    entity = _load_entity(db, request.entity_type, request.entity_id)
    audit_service.record(
        db, actor=approver, entity_type=request.entity_type.value, entity_id=request.entity_id,
        action="approval_step_approved" if approve else "approval_step_rejected",
        payload={"sequence": request.sequence, "role": request.required_role.value,
                 "comment": comment or ""},
    )

    if not approve:
        remaining = db.execute(
            select(ApprovalRequest).where(
                ApprovalRequest.entity_type == request.entity_type,
                ApprovalRequest.entity_id == request.entity_id,
                ApprovalRequest.status == ApprovalStatus.PENDING,
            )
        ).scalars().all()
        for step in remaining:
            step.status = ApprovalStatus.REJECTED
            step.comment = f"Auto-closed: chain rejected at step {request.sequence}"
            step.decided_at = datetime.now(timezone.utc)
        _finalize_rejected(db, request.entity_type, entity, approver, comment)
        db.commit()
        return {"chain_complete": True, "entity_status": entity.status.value}

    still_pending = db.execute(
        select(ApprovalRequest).where(
            ApprovalRequest.entity_type == request.entity_type,
            ApprovalRequest.entity_id == request.entity_id,
            ApprovalRequest.status == ApprovalStatus.PENDING,
        ).limit(1)
    ).scalar_one_or_none()
    if still_pending is None:
        _finalize_approved(db, request.entity_type, entity, approver)
        db.commit()
        return {"chain_complete": True, "entity_status": entity.status.value}

    db.commit()
    return {"chain_complete": False, "entity_status": entity.status.value}


def pending_for_user(db: Session, user: User) -> list[ApprovalRequest]:
    query = select(ApprovalRequest).where(ApprovalRequest.status == ApprovalStatus.PENDING)
    if user.role != UserRole.ADMIN:
        query = query.where(ApprovalRequest.required_role == user.role)
    return db.execute(query.order_by(ApprovalRequest.created_at.asc())).scalars().all()


def requests_for_entity(db: Session, entity_type: ApprovalEntityType, entity_id: int) -> list[ApprovalRequest]:
    return db.execute(
        select(ApprovalRequest)
        .where(ApprovalRequest.entity_type == entity_type, ApprovalRequest.entity_id == entity_id)
        .order_by(ApprovalRequest.sequence.asc())
    ).scalars().all()
