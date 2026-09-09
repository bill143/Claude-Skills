"""End-to-end smoke test against a throwaway SQLite database.

Exercises the full control loop:
  login -> project/budget/vendor setup -> approval rules -> PCO lifecycle
  (draft -> pricing -> submitted -> convert) -> SCO & OCO approval chains ->
  PO from SCO -> PO approval -> commitments -> cost posting -> EAC/ETC ->
  KPIs -> audit chain verification -> rejection + sequence-enforcement paths.

Run from the project root:  python scripts/smoke_test.py
Exits non-zero on the first failed assertion.
"""
import os
import sys
import tempfile

os.environ["DATABASE_URL"] = "sqlite:///" + os.path.join(tempfile.mkdtemp(), "smoke.db")
os.environ["AUTO_CREATE_TABLES"] = "true"

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi.testclient import TestClient  # noqa: E402

from app.core.security import hash_password  # noqa: E402
from app.db import base  # noqa: F401, E402
from app.db.base_class import Base  # noqa: E402
from app.db.session import SessionLocal, engine  # noqa: E402
from app.main import app  # noqa: E402
from app.models import User, UserRole  # noqa: E402

PASSWORD = "Test123!"


def bootstrap_admin() -> None:
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    db.add(User(email="admin@test.io", full_name="Admin", role=UserRole.ADMIN,
                hashed_password=hash_password(PASSWORD)))
    db.commit()
    db.close()


def login(client: TestClient, email: str) -> dict:
    resp = client.post("/api/v1/auth/login", data={"username": email, "password": PASSWORD})
    assert resp.status_code == 200, resp.text
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


def main() -> None:  # noqa: PLR0915
    bootstrap_admin()
    with TestClient(app) as client:
        admin = login(client, "admin@test.io")

        # --- users -----------------------------------------------------------
        for email, role in (("pm@test.io", "PROJECT_MANAGER"), ("exec@test.io", "EXECUTIVE"),
                            ("fin@test.io", "FINANCE")):
            resp = client.post("/api/v1/auth/users", headers=admin,
                               json={"email": email, "full_name": email.split("@")[0],
                                     "password": PASSWORD, "role": role})
            assert resp.status_code == 201, resp.text
        pm = login(client, "pm@test.io")
        boss = login(client, "exec@test.io")

        # --- approval matrix -------------------------------------------------
        rules = [
            ("CHANGE_ORDER", "PROJECT_MANAGER", 0, 1), ("CHANGE_ORDER", "EXECUTIVE", 50000, 2),
            ("CHANGE_ORDER", "FINANCE", 100000, 3),
            ("PURCHASE_ORDER", "PROJECT_MANAGER", 0, 1), ("PURCHASE_ORDER", "EXECUTIVE", 100000, 2),
        ]
        for entity_type, role, threshold, sequence in rules:
            resp = client.post("/api/v1/approvals/rules", headers=admin,
                               json={"entity_type": entity_type, "role": role,
                                     "threshold_amount": threshold, "sequence": sequence})
            assert resp.status_code == 201, resp.text

        # --- project / budget / vendor --------------------------------------
        resp = client.post("/api/v1/projects", headers=pm,
                           json={"code": "T-001", "name": "Test Tower",
                                 "original_contract_value": 5000000, "budget_control": "WARN"})
        assert resp.status_code == 201, resp.text
        project_id = resp.json()["id"]

        lines = {}
        for code, budget in (("03-300", 1000000), ("05-100", 750000)):
            resp = client.post(f"/api/v1/projects/{project_id}/budget-lines", headers=pm,
                               json={"cost_code": code, "description": code,
                                     "category": "SUBCONTRACT", "original_budget": budget})
            assert resp.status_code == 201, resp.text
            lines[code] = resp.json()["id"]

        resp = client.post("/api/v1/vendors", headers=pm,
                           json={"name": "Acme Concrete", "vendor_type": "SUBCONTRACTOR"})
        assert resp.status_code == 201, resp.text
        vendor_id = resp.json()["id"]

        # --- PCO lifecycle ---------------------------------------------------
        resp = client.post(f"/api/v1/projects/{project_id}/change-orders", headers=pm,
                           json={"co_type": "PCO", "title": "Skylight",
                                 "schedule_impact_days": 5,
                                 "lines": [
                                     {"budget_line_id": lines["03-300"],
                                      "description": "Deck mods", "quantity": 1, "unit_cost": 60000},
                                     {"budget_line_id": lines["05-100"],
                                      "description": "Framing", "quantity": 1, "unit_cost": 15000},
                                 ]})
        assert resp.status_code == 201, resp.text
        pco = resp.json()
        assert pco["number"] == "PCO-0001" and pco["total_amount"] == 75000.0

        for action, expected in (("send_to_pricing", "PRICING"), ("submit", "SUBMITTED")):
            resp = client.post(f"/api/v1/change-orders/{pco['id']}/transition", headers=pm,
                               json={"action": action})
            assert resp.status_code == 200, resp.text
            assert resp.json()["status"] == expected

        # Illegal transition is rejected.
        resp = client.post(f"/api/v1/change-orders/{pco['id']}/transition", headers=pm,
                           json={"action": "send_to_pricing"})
        assert resp.status_code == 422, resp.text

        # Convert -> SCO (cost) + OCO (cost + 10% markup).
        resp = client.post(f"/api/v1/change-orders/{pco['id']}/convert", headers=pm,
                           json={"targets": ["OCO", "SCO"], "vendor_id": vendor_id,
                                 "oco_markup_pct": 0.10})
        assert resp.status_code == 200, resp.text
        created = {d["co_type"]: d for d in resp.json()}
        sco, oco = created["SCO"], created["OCO"]
        assert sco["total_amount"] == 75000.0 and oco["total_amount"] == 82500.0
        assert client.get(f"/api/v1/change-orders/{pco['id']}",
                          headers=pm).json()["status"] == "CONVERTED"

        # --- SCO approval chain: PM then EXEC (75k >= 50k) -------------------
        resp = client.post(f"/api/v1/change-orders/{sco['id']}/transition", headers=pm,
                           json={"action": "submit_for_approval"})
        assert resp.status_code == 200 and resp.json()["status"] == "PENDING_APPROVAL"
        steps = client.get(f"/api/v1/change-orders/{sco['id']}/approvals", headers=pm).json()
        assert [s["required_role"] for s in steps] == ["PROJECT_MANAGER", "EXECUTIVE"]

        # Sequence enforcement: EXEC cannot decide step 2 before step 1.
        resp = client.post(f"/api/v1/approvals/{steps[1]['id']}/decide", headers=boss,
                           json={"approve": True})
        assert resp.status_code == 409, resp.text
        # Role enforcement: EXEC cannot take the PM step.
        resp = client.post(f"/api/v1/approvals/{steps[0]['id']}/decide", headers=boss,
                           json={"approve": True})
        assert resp.status_code == 403, resp.text

        resp = client.post(f"/api/v1/approvals/{steps[0]['id']}/decide", headers=pm,
                           json={"approve": True, "comment": "ok"})
        assert resp.status_code == 200 and resp.json()["chain_complete"] is False
        resp = client.post(f"/api/v1/approvals/{steps[1]['id']}/decide", headers=boss,
                           json={"approve": True})
        assert resp.status_code == 200
        assert resp.json() == {"chain_complete": True, "entity_status": "APPROVED"}

        # SCO commitment now visible in the forecast.
        totals = client.get(f"/api/v1/projects/{project_id}/forecast",
                            headers=pm).json()["totals"]
        assert totals["committed"] == 75000.0, totals

        # --- OCO approval -> budget revision ---------------------------------
        resp = client.post(f"/api/v1/change-orders/{oco['id']}/transition", headers=pm,
                           json={"action": "submit_for_approval"})
        assert resp.status_code == 200
        steps = client.get(f"/api/v1/change-orders/{oco['id']}/approvals", headers=pm).json()
        for step, headers in zip(steps, (pm, boss), strict=True):
            resp = client.post(f"/api/v1/approvals/{step['id']}/decide", headers=headers,
                               json={"approve": True})
            assert resp.status_code == 200, resp.text
        totals = client.get(f"/api/v1/projects/{project_id}/forecast",
                            headers=pm).json()["totals"]
        assert totals["approved_changes"] == 82500.0
        assert totals["current_budget"] == 1832500.0  # 1.75M + 82.5k

        # --- PO from approved SCO -> approval -> supersedes SCO commitment ---
        resp = client.post(f"/api/v1/projects/{project_id}/purchase-orders", headers=pm,
                           json={"vendor_id": vendor_id, "source_change_order_id": sco["id"]})
        assert resp.status_code == 201, resp.text
        po = resp.json()
        assert po["number"] == "PO-0001" and po["total_amount"] == 75000.0

        resp = client.post(f"/api/v1/purchase-orders/{po['id']}/submit", headers=pm)
        assert resp.status_code == 200, resp.text
        assert resp.json()["approval_steps"] == 1  # 75k < 100k -> PM only
        step = client.get(f"/api/v1/purchase-orders/{po['id']}/approvals", headers=pm).json()[0]
        resp = client.post(f"/api/v1/approvals/{step['id']}/decide", headers=pm,
                           json={"approve": True})
        assert resp.json()["entity_status"] == "APPROVED"

        # No double counting: PO replaced the SCO as the commitment source.
        totals = client.get(f"/api/v1/projects/{project_id}/forecast",
                            headers=pm).json()["totals"]
        assert totals["committed"] == 75000.0, totals

        # --- actuals + EAC/ETC ----------------------------------------------
        from datetime import date
        resp = client.post(f"/api/v1/budget-lines/{lines['03-300']}/costs", headers=pm,
                           json={"entry_date": str(date.today()), "amount": 30000,
                                 "description": "First draw"})
        assert resp.status_code == 201, resp.text

        forecast = client.get(f"/api/v1/projects/{project_id}/forecast", headers=pm).json()
        concrete = next(r for r in forecast["lines"] if r["cost_code"] == "03-300")
        # current 1,066,000 / committed 60,000 / actual 30,000
        # EAC = max(60000, 30000) + (1066000 - 60000) = 1,066,000 ; ETC = 1,036,000
        assert concrete["current_budget"] == 1066000.0
        assert concrete["committed"] == 60000.0
        assert concrete["eac"] == 1066000.0 and concrete["etc"] == 1036000.0
        assert concrete["vac"] == 0.0

        cpi = client.get(f"/api/v1/projects/{project_id}/forecast", headers=pm,
                         params={"method": "CPI", "percent_complete": 0.5}).json()
        concrete_cpi = next(r for r in cpi["lines"] if r["cost_code"] == "03-300")
        assert concrete_cpi["eac"] == 60000.0  # EAC = BAC/CPI = actual/pct

        kpis = client.get(f"/api/v1/projects/{project_id}/kpis", headers=pm).json()
        assert kpis["contract_value"] == 5082500.0  # 5M + 82.5k OCO
        assert kpis["committed"] == 75000.0 and kpis["actual_to_date"] == 30000.0
        assert kpis["burn_rate_30d"] == 30000.0

        snapshot = client.post(f"/api/v1/projects/{project_id}/forecast/snapshot",
                               headers=pm)
        assert snapshot.status_code == 201, snapshot.text

        # --- budget WARN path ------------------------------------------------
        resp = client.post(f"/api/v1/projects/{project_id}/purchase-orders", headers=pm,
                           json={"vendor_id": vendor_id,
                                 "lines": [{"budget_line_id": lines["05-100"],
                                            "description": "Big buy", "quantity": 1,
                                            "unit_cost": 2000000}]})
        big_po = resp.json()
        resp = client.post(f"/api/v1/purchase-orders/{big_po['id']}/submit", headers=pm)
        assert resp.status_code == 200 and len(resp.json()["budget_warnings"]) == 1

        # --- rejection + revise path -----------------------------------------
        resp = client.post(f"/api/v1/projects/{project_id}/change-orders", headers=pm,
                           json={"co_type": "SCO", "title": "Extra rebar",
                                 "vendor_id": vendor_id,
                                 "lines": [{"budget_line_id": lines["03-300"],
                                            "description": "Rebar", "quantity": 1,
                                            "unit_cost": 20000}]})
        sco2 = resp.json()
        client.post(f"/api/v1/change-orders/{sco2['id']}/transition", headers=pm,
                    json={"action": "submit_for_approval"})
        step = client.get(f"/api/v1/change-orders/{sco2['id']}/approvals", headers=pm).json()[0]
        resp = client.post(f"/api/v1/approvals/{step['id']}/decide", headers=pm,
                           json={"approve": False, "comment": "price too high"})
        assert resp.json()["entity_status"] == "REJECTED"
        resp = client.post(f"/api/v1/change-orders/{sco2['id']}/transition", headers=pm,
                           json={"action": "revise"})
        assert resp.json()["status"] == "DRAFT"

        # --- audit ledger ----------------------------------------------------
        verify = client.get("/api/v1/audit/verify", headers=admin).json()
        assert verify["valid"] is True and verify["events"] > 25, verify

    print("SMOKE TEST PASSED — full PCO→OCO/SCO→PO→forecast→audit loop verified "
          f"({verify['events']} audit events, chain intact).")


if __name__ == "__main__":
    main()
