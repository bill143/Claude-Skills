"""Shared fixtures: isolated SQLite DB, seeded users/rules, authed clients.

Environment is pinned BEFORE any app import so the cached Settings singleton
picks up the test database and disables rate limiting.
"""
import os
import sys
import tempfile
import uuid

os.environ["DATABASE_URL"] = os.environ.get(
    "TEST_DATABASE_URL", "sqlite:///" + os.path.join(tempfile.mkdtemp(), "test.db")
)
os.environ["ENVIRONMENT"] = "dev"
os.environ["AUTO_CREATE_TABLES"] = "false"
os.environ["RATE_LIMIT_ENABLED"] = "false"

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

PASSWORD = "Test123!"

CO_RULES = [("PROJECT_MANAGER", 0, 1), ("EXECUTIVE", 50000, 2), ("FINANCE", 100000, 3)]
PO_RULES = [("PROJECT_MANAGER", 0, 1), ("EXECUTIVE", 100000, 2)]


@pytest.fixture(scope="session")
def client():
    from decimal import Decimal

    from app.core.security import hash_password
    from app.db import base  # noqa: F401
    from app.db.base_class import Base
    from app.db.session import SessionLocal, engine
    from app.main import app
    from app.models import ApprovalEntityType, ApprovalRule, User, UserRole

    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    for email, role in (
        ("admin@test.io", UserRole.ADMIN),
        ("pm@test.io", UserRole.PROJECT_MANAGER),
        ("exec@test.io", UserRole.EXECUTIVE),
        ("fin@test.io", UserRole.FINANCE),
        ("viewer@test.io", UserRole.VIEWER),
    ):
        db.add(User(email=email, full_name=email.split("@")[0], role=role,
                    hashed_password=hash_password(PASSWORD)))
    for role, threshold, sequence in CO_RULES:
        db.add(ApprovalRule(entity_type=ApprovalEntityType.CHANGE_ORDER, role=UserRole(role),
                            threshold_amount=Decimal(threshold), sequence=sequence))
    for role, threshold, sequence in PO_RULES:
        db.add(ApprovalRule(entity_type=ApprovalEntityType.PURCHASE_ORDER, role=UserRole(role),
                            threshold_amount=Decimal(threshold), sequence=sequence))
    db.commit()
    db.close()

    with TestClient(app) as test_client:
        yield test_client


def _login(client: TestClient, email: str) -> dict:
    resp = client.post("/api/v1/auth/login", data={"username": email, "password": PASSWORD})
    assert resp.status_code == 200, resp.text
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


@pytest.fixture(scope="session")
def admin(client):
    return _login(client, "admin@test.io")


@pytest.fixture(scope="session")
def pm(client):
    return _login(client, "pm@test.io")


@pytest.fixture(scope="session")
def boss(client):
    return _login(client, "exec@test.io")


@pytest.fixture(scope="session")
def fin(client):
    return _login(client, "fin@test.io")


@pytest.fixture(scope="session")
def viewer(client):
    return _login(client, "viewer@test.io")


@pytest.fixture
def project(client, pm):
    """Fresh project + two budget lines + a vendor, unique per test."""
    code = f"T-{uuid.uuid4().hex[:8]}"
    resp = client.post("/api/v1/projects", headers=pm,
                       json={"code": code, "name": f"Test {code}",
                             "original_contract_value": 5000000, "budget_control": "WARN"})
    assert resp.status_code == 201, resp.text
    project_id = resp.json()["id"]
    lines = {}
    for cost_code, budget in (("03-300", 1000000), ("05-100", 750000)):
        resp = client.post(f"/api/v1/projects/{project_id}/budget-lines", headers=pm,
                           json={"cost_code": cost_code, "description": cost_code,
                                 "category": "SUBCONTRACT", "original_budget": budget})
        assert resp.status_code == 201, resp.text
        lines[cost_code] = resp.json()["id"]
    resp = client.post("/api/v1/vendors", headers=pm,
                       json={"name": f"Vendor {code}", "vendor_type": "SUBCONTRACTOR"})
    assert resp.status_code == 201, resp.text
    return {"id": project_id, "lines": lines, "vendor_id": resp.json()["id"]}


def make_sco(client, headers, project, amount, title="Test SCO"):
    """Create a draft SCO with a single line of the given amount."""
    resp = client.post(f"/api/v1/projects/{project['id']}/change-orders", headers=headers,
                       json={"co_type": "SCO", "title": title,
                             "vendor_id": project["vendor_id"],
                             "lines": [{"budget_line_id": project["lines"]["03-300"],
                                        "description": "work", "quantity": 1,
                                        "unit_cost": amount}]})
    assert resp.status_code == 201, resp.text
    return resp.json()
