"""Seed the database with demo users, a project, budget, vendors, and rules.

Run from the project root:  python scripts/seed.py
Idempotent: re-running skips anything that already exists.
"""
import os
import sys
from datetime import date, timedelta
from decimal import Decimal

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import select  # noqa: E402

from app.core.security import hash_password  # noqa: E402
from app.db import base  # noqa: F401, E402  (registers all models)
from app.db.base_class import Base  # noqa: E402
from app.db.session import SessionLocal, engine  # noqa: E402
from app.models import (  # noqa: E402
    ApprovalEntityType,
    ApprovalRule,
    BudgetControlAction,
    BudgetLine,
    ChangeOrder,
    ChangeOrderLine,
    ChangeOrderType,
    CostCategory,
    CostEntry,
    Project,
    User,
    UserRole,
    Vendor,
    VendorType,
)

PASSWORD = "ChangeMe123!"

USERS = [
    ("admin@example.com", "Alex Admin", UserRole.ADMIN),
    ("pm@example.com", "Pat Manager", UserRole.PROJECT_MANAGER),
    ("exec@example.com", "Erin Executive", UserRole.EXECUTIVE),
    ("finance@example.com", "Fran Finance", UserRole.FINANCE),
]

VENDORS = [
    ("Summit Concrete LLC", VendorType.SUBCONTRACTOR, "Concrete"),
    ("Ironclad Steel Erectors", VendorType.SUBCONTRACTOR, "Structural Steel"),
    ("Metro Building Supply", VendorType.SUPPLIER, "Materials"),
]

BUDGET_LINES = [
    ("01-000", "General Conditions", CostCategory.GENERAL_CONDITIONS, "450000"),
    ("03-300", "Cast-in-Place Concrete", CostCategory.SUBCONTRACT, "1200000"),
    ("05-100", "Structural Steel", CostCategory.SUBCONTRACT, "950000"),
    ("06-100", "Rough Carpentry", CostCategory.LABOR, "380000"),
    ("09-900", "Finishes", CostCategory.MATERIAL, "620000"),
    ("15-000", "Mechanical / Plumbing", CostCategory.SUBCONTRACT, "1100000"),
]

APPROVAL_RULES = [
    (ApprovalEntityType.CHANGE_ORDER, UserRole.PROJECT_MANAGER, "0", 1, "PM approves all COs"),
    (ApprovalEntityType.CHANGE_ORDER, UserRole.EXECUTIVE, "50000", 2, "Executive above $50k"),
    (ApprovalEntityType.CHANGE_ORDER, UserRole.FINANCE, "100000", 3, "Finance above $100k"),
    (ApprovalEntityType.PURCHASE_ORDER, UserRole.PROJECT_MANAGER, "0", 1, "PM approves all POs"),
    (ApprovalEntityType.PURCHASE_ORDER, UserRole.EXECUTIVE, "100000", 2, "Executive above $100k"),
]


def main() -> None:
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        for email, name, role in USERS:
            if not db.execute(select(User).where(User.email == email)).scalar_one_or_none():
                db.add(User(email=email, full_name=name, role=role,
                            hashed_password=hash_password(PASSWORD)))
        db.flush()

        for name, vtype, trade in VENDORS:
            if not db.execute(select(Vendor).where(Vendor.name == name)).scalar_one_or_none():
                db.add(Vendor(name=name, vendor_type=vtype, trade=trade))
        db.flush()

        project = db.execute(select(Project).where(Project.code == "PRJ-001")).scalar_one_or_none()
        if project is None:
            project = Project(
                code="PRJ-001",
                name="Riverside Medical Office Building",
                owner_name="Riverside Health Partners",
                original_contract_value=Decimal("5600000"),
                budget_control=BudgetControlAction.WARN,
                start_date=date.today() - timedelta(days=120),
                end_date=date.today() + timedelta(days=420),
            )
            db.add(project)
            db.flush()

            for code, desc, category, amount in BUDGET_LINES:
                db.add(BudgetLine(project_id=project.id, cost_code=code, description=desc,
                                  category=category, original_budget=Decimal(amount)))
            db.flush()

            concrete = db.execute(
                select(BudgetLine).where(BudgetLine.project_id == project.id,
                                         BudgetLine.cost_code == "03-300")
            ).scalar_one()
            steel = db.execute(
                select(BudgetLine).where(BudgetLine.project_id == project.id,
                                         BudgetLine.cost_code == "05-100")
            ).scalar_one()

            # Historic actuals so the dashboard has a burn rate out of the box.
            for offset, amount in ((70, "180000"), (40, "220000"), (12, "160000")):
                db.add(CostEntry(budget_line_id=concrete.id,
                                 entry_date=date.today() - timedelta(days=offset),
                                 amount=Decimal(amount), description="Progress billing"))
            db.add(CostEntry(budget_line_id=steel.id,
                             entry_date=date.today() - timedelta(days=20),
                             amount=Decimal("140000"), description="Steel delivery draw"))

            pco = ChangeOrder(
                project_id=project.id,
                number="PCO-0001",
                co_type=ChangeOrderType.PCO,
                title="Owner-requested lobby skylight",
                description="Add structural framing and glazing for a 30x20 lobby skylight.",
                schedule_impact_days=10,
            )
            db.add(pco)
            db.flush()
            db.add(ChangeOrderLine(change_order_id=pco.id, budget_line_id=steel.id,
                                   description="Skylight structural framing",
                                   quantity=Decimal("1"), unit_cost=Decimal("48000"),
                                   amount=Decimal("48000")))
            db.add(ChangeOrderLine(change_order_id=pco.id, budget_line_id=concrete.id,
                                   description="Curb and deck modifications",
                                   quantity=Decimal("1"), unit_cost=Decimal("14500"),
                                   amount=Decimal("14500")))

        if not db.execute(select(ApprovalRule)).scalars().first():
            for entity_type, role, threshold, sequence, description in APPROVAL_RULES:
                db.add(ApprovalRule(entity_type=entity_type, role=role,
                                    threshold_amount=Decimal(threshold),
                                    sequence=sequence, description=description))

        db.commit()
        print("Seed complete.")
        print(f"  Users ({PASSWORD}): " + ", ".join(email for email, *_ in USERS))
        print("  Project: PRJ-001 Riverside Medical Office Building")
        print("  Sample PCO-0001 ready to move through the workflow.")
    finally:
        db.close()


if __name__ == "__main__":
    main()
