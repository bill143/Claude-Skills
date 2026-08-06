from datetime import date

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import CostCategory, ForecastMethod


class BudgetLineCreate(BaseModel):
    cost_code: str
    description: str
    category: CostCategory = CostCategory.GENERAL_CONDITIONS
    original_budget: float = Field(ge=0)


class BudgetLineOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    project_id: int
    cost_code: str
    description: str
    category: CostCategory
    original_budget: float


class BudgetLineMetrics(BaseModel):
    id: int
    cost_code: str
    description: str
    category: str
    original_budget: float
    approved_changes: float
    current_budget: float
    committed: float
    actual: float
    etc: float
    eac: float
    vac: float
    method: str


class ProjectForecastOut(BaseModel):
    project_id: int
    method: str
    lines: list[BudgetLineMetrics]
    totals: dict[str, float]


class CostEntryCreate(BaseModel):
    entry_date: date
    amount: float
    description: str | None = None


class CostEntryOut(CostEntryCreate):
    model_config = ConfigDict(from_attributes=True)

    id: int
    budget_line_id: int


class ForecastSnapshotOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    project_id: int
    as_of: date
    method: ForecastMethod
    total_current_budget: float
    total_committed: float
    total_actual: float
    total_etc: float
    total_eac: float
    total_vac: float
