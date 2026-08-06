from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import ChangeOrderStatus, ChangeOrderType


class ChangeOrderLineIn(BaseModel):
    budget_line_id: int
    description: str
    quantity: float = Field(default=1, gt=0)
    unit_cost: float = Field(default=0, ge=0)


class ChangeOrderLineOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    budget_line_id: int
    description: str
    quantity: float
    unit_cost: float
    amount: float


class ChangeOrderCreate(BaseModel):
    co_type: ChangeOrderType = ChangeOrderType.PCO
    title: str
    description: str | None = None
    vendor_id: int | None = None  # required for SCO
    schedule_impact_days: int = 0
    lines: list[ChangeOrderLineIn] = []


class ChangeOrderOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    project_id: int
    number: str
    co_type: ChangeOrderType
    status: ChangeOrderStatus
    title: str
    description: str | None
    vendor_id: int | None
    origin_pco_id: int | None
    schedule_impact_days: int
    total_amount: float
    lines: list[ChangeOrderLineOut]
    created_at: datetime
    allowed_actions: list[str] = []


class TransitionIn(BaseModel):
    action: str


class ConvertIn(BaseModel):
    targets: list[ChangeOrderType]  # OCO and/or SCO
    vendor_id: int | None = None  # required when SCO in targets
    oco_markup_pct: float = Field(default=0.0, ge=0, le=1.0)
