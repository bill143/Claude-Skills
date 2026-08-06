from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import PurchaseOrderStatus


class PurchaseOrderLineIn(BaseModel):
    budget_line_id: int
    description: str
    quantity: float = Field(default=1, gt=0)
    unit_cost: float = Field(default=0, ge=0)


class PurchaseOrderLineOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    budget_line_id: int
    description: str
    quantity: float
    unit_cost: float
    amount: float


class PurchaseOrderCreate(BaseModel):
    vendor_id: int
    source_change_order_id: int | None = None  # create from an approved SCO
    issued_date: date | None = None
    notes: str | None = None
    lines: list[PurchaseOrderLineIn] = []  # ignored when sourced from an SCO


class PurchaseOrderOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    project_id: int
    number: str
    vendor_id: int
    status: PurchaseOrderStatus
    source_change_order_id: int | None
    issued_date: date | None
    notes: str | None
    total_amount: float
    lines: list[PurchaseOrderLineOut]
    created_at: datetime


class POSubmitResult(BaseModel):
    status: str
    budget_warnings: list[dict]
    approval_steps: int


class POTransitionIn(BaseModel):
    action: str
