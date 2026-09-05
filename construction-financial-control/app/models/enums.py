"""Domain enums.

All enums are str-based so they serialize cleanly in JSON and are stored as
plain VARCHAR (native_enum=False) for cross-database portability.
"""
import enum


class UserRole(str, enum.Enum):
    ADMIN = "ADMIN"
    PROJECT_MANAGER = "PROJECT_MANAGER"
    EXECUTIVE = "EXECUTIVE"
    FINANCE = "FINANCE"
    VIEWER = "VIEWER"


class VendorType(str, enum.Enum):
    SUBCONTRACTOR = "SUBCONTRACTOR"
    SUPPLIER = "SUPPLIER"


class CostCategory(str, enum.Enum):
    LABOR = "LABOR"
    MATERIAL = "MATERIAL"
    EQUIPMENT = "EQUIPMENT"
    SUBCONTRACT = "SUBCONTRACT"
    GENERAL_CONDITIONS = "GENERAL_CONDITIONS"


class ChangeOrderType(str, enum.Enum):
    PCO = "PCO"  # Potential Change Order (internal pricing vehicle)
    OCO = "OCO"  # Owner Change Order (revenue + budget side)
    SCO = "SCO"  # Subcontractor Change Order (commitment side)


class ChangeOrderStatus(str, enum.Enum):
    DRAFT = "DRAFT"
    PRICING = "PRICING"  # PCO only: RFQs out to subcontractors
    SUBMITTED = "SUBMITTED"  # PCO only: priced, awaiting disposition
    PENDING_APPROVAL = "PENDING_APPROVAL"  # OCO/SCO: approval chain in flight
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    CONVERTED = "CONVERTED"  # PCO that produced OCO/SCO documents
    VOID = "VOID"


class PurchaseOrderStatus(str, enum.Enum):
    DRAFT = "DRAFT"
    PENDING_APPROVAL = "PENDING_APPROVAL"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    CLOSED = "CLOSED"
    CANCELLED = "CANCELLED"


class ApprovalEntityType(str, enum.Enum):
    CHANGE_ORDER = "CHANGE_ORDER"
    PURCHASE_ORDER = "PURCHASE_ORDER"


class ApprovalStatus(str, enum.Enum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"


class BudgetControlAction(str, enum.Enum):
    """What happens when a PO would push commitments past current budget.

    Pattern borrowed from ERPNext's Budget doctype (Stop / Warn / Ignore).
    """

    STOP = "STOP"
    WARN = "WARN"
    IGNORE = "IGNORE"


class ForecastMethod(str, enum.Enum):
    REMAINING_BUDGET = "REMAINING_BUDGET"  # EAC = max(current budget, committed, actual)
    CPI = "CPI"  # EAC = current_budget / CPI (earned-value method)
    MANUAL = "MANUAL"  # per-line PM override: EAC = actual + manual ETC
