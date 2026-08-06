from datetime import date
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import BudgetControlAction


class ProjectCreate(BaseModel):
    code: str
    name: str
    owner_name: str | None = None
    original_contract_value: Decimal = Field(default=Decimal("0"), ge=0, max_digits=16,
                                             decimal_places=2)
    budget_control: BudgetControlAction = BudgetControlAction.WARN
    start_date: date | None = None
    end_date: date | None = None


class ProjectOut(ProjectCreate):
    model_config = ConfigDict(from_attributes=True)

    id: int
    is_active: bool
