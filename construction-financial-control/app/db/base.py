"""Import all models so Base.metadata knows every table.

Used by Alembic autogenerate and by create_all() in dev/seed paths.
"""
from app.db.base_class import Base  # noqa: F401
from app.models.user import User  # noqa: F401
from app.models.vendor import Vendor  # noqa: F401
from app.models.project import Project  # noqa: F401
from app.models.budget import BudgetLine, CostEntry, ForecastSnapshot  # noqa: F401
from app.models.change_order import ChangeOrder, ChangeOrderLine  # noqa: F401
from app.models.purchase_order import PurchaseOrder, PurchaseOrderLine  # noqa: F401
from app.models.approval import ApprovalRule, ApprovalRequest  # noqa: F401
from app.models.audit import AuditEvent  # noqa: F401
