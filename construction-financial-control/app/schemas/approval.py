from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import ApprovalEntityType, ApprovalStatus, UserRole


class ApprovalRuleCreate(BaseModel):
    entity_type: ApprovalEntityType
    role: UserRole
    threshold_amount: Decimal = Field(default=Decimal("0"), ge=0, max_digits=16, decimal_places=2)
    sequence: int = 1
    description: str | None = None


class ApprovalRuleOut(ApprovalRuleCreate):
    model_config = ConfigDict(from_attributes=True)

    id: int


class ApprovalRequestOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    entity_type: ApprovalEntityType
    entity_id: int
    sequence: int
    required_role: UserRole
    status: ApprovalStatus
    approver_id: int | None
    comment: str | None
    decided_at: datetime | None
    created_at: datetime


class DecisionIn(BaseModel):
    approve: bool
    comment: str | None = None


class DecisionOut(BaseModel):
    chain_complete: bool
    entity_status: str
