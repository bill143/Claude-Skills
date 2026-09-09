from datetime import date
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import CostCategory, ForecastMethod

# Money enters the API as Decimal (pydantic parses JSON numbers/strings via
# str, never binary float) and is stored as Numeric(16,2). Output schemas use
# float only for cent-quantized display values, which are IEEE-754 exact.


class BudgetLineCreate(BaseModel):
    cost_code: str
    # Optional: blank auto-fills from the CSI MasterFormat library by code.
    description: str | None = None
    category: CostCategory = CostCategory.GENERAL_CONDITIONS
    original_budget: Decimal = Field(ge=0, max_digits=16, decimal_places=2)


class BudgetLineOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    project_id: int
    cost_code: str
    description: str
    category: CostCategory
    original_budget: float
    manual_etc: float | None = None


class BudgetLinePatch(BaseModel):
    """Editable line fields. Budget amounts change only via change orders."""

    description: str | None = None
    manual_etc: Decimal | None = Field(default=None, ge=0, max_digits=16, decimal_places=2)
    clear_manual_etc: bool = False


class BudgetLineMetrics(BaseModel):
    id: int
    cost_code: str
    division: str
    description: str
    category: str
    manual_etc: float | None = None
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
    # Negative amounts are legal (credit memos / cost reversals).
    amount: Decimal = Field(max_digits=16, decimal_places=2)
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
