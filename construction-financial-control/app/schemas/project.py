from datetime import date

from pydantic import BaseModel, ConfigDict

from app.models.enums import BudgetControlAction


class ProjectCreate(BaseModel):
    code: str
    name: str
    owner_name: str | None = None
    original_contract_value: float = 0.0
    budget_control: BudgetControlAction = BudgetControlAction.WARN
    start_date: date | None = None
    end_date: date | None = None


class ProjectOut(ProjectCreate):
    model_config = ConfigDict(from_attributes=True)

    id: int
    is_active: bool
