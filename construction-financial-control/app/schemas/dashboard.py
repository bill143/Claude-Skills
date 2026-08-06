from pydantic import BaseModel


class ProjectKpis(BaseModel):
    project_id: int
    project_code: str
    contract_value: float
    original_budget: float
    approved_changes: float
    current_budget: float
    committed: float
    actual_to_date: float
    etc: float
    eac: float
    vac: float
    projected_margin: float
    burn_rate_30d: float
    percent_complete: float
    method: str
    open_pcos: int = 0
    pending_approvals: int = 0


class AuditVerifyOut(BaseModel):
    valid: bool
    events: int
    first_broken_event_id: int | None
    reason: str | None
