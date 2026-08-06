from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.audit import AuditEvent
from app.models.user import User
from app.schemas.dashboard import AuditVerifyOut
from app.services import audit_service

router = APIRouter(prefix="/audit", tags=["audit"])


@router.get("")
def list_audit_events(
    entity_type: str | None = Query(default=None),
    entity_id: int | None = Query(default=None),
    limit: int = Query(default=100, le=1000),
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    query = select(AuditEvent)
    if entity_type:
        query = query.where(AuditEvent.entity_type == entity_type)
    if entity_id is not None:
        query = query.where(AuditEvent.entity_id == entity_id)
    events = db.execute(query.order_by(AuditEvent.id.desc()).limit(limit)).scalars().all()
    return [
        {
            "id": e.id,
            "entity_type": e.entity_type,
            "entity_id": e.entity_id,
            "action": e.action,
            "actor_id": e.actor_id,
            "payload": e.payload,
            "hash": e.hash,
            "created_at": e.created_at.isoformat(),
        }
        for e in events
    ]


@router.get("/verify", response_model=AuditVerifyOut)
def verify_audit_chain(db: Session = Depends(get_db), _user: User = Depends(get_current_user)):
    return audit_service.verify_chain(db)
