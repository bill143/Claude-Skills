"""Regression tests for the Copilot/Codex review findings on PR #2.

Covers: per-budget-line aggregation in the PO budget check, pending-PO
reservation, source-SCO offset during buyout, one-buyout-per-SCO, audit
actor tamper detection, and project-scoped pending-approval KPIs.
"""
import uuid

import pytest
from sqlalchemy import text

from tests.conftest import make_sco


def _stop_project(client, pm, budget: int):
    """Project with budget_control=STOP, one budget line, one vendor."""
    code = f"S-{uuid.uuid4().hex[:8]}"
    project = client.post("/api/v1/projects", headers=pm,
                          json={"code": code, "name": f"Stop {code}",
                                "original_contract_value": budget * 2,
                                "budget_control": "STOP"}).json()
    line = client.post(f"/api/v1/projects/{project['id']}/budget-lines", headers=pm,
                       json={"cost_code": "03 30 00", "category": "SUBCONTRACT",
                             "original_budget": budget}).json()
    vendor = client.post("/api/v1/vendors", headers=pm,
                         json={"name": f"V {code}", "vendor_type": "SUBCONTRACTOR"}).json()
    return {"id": project["id"], "lines": {"03-300": line["id"]}, "vendor_id": vendor["id"]}


def _manual_po(client, pm, project, amounts: list[int]):
    resp = client.post(f"/api/v1/projects/{project['id']}/purchase-orders", headers=pm,
                       json={"vendor_id": project["vendor_id"],
                             "lines": [{"budget_line_id": project["lines"]["03-300"],
                                        "description": f"line {i}", "quantity": 1,
                                        "unit_cost": amount}
                                       for i, amount in enumerate(amounts)]})
    assert resp.status_code == 201, resp.text
    return resp.json()


def test_budget_check_aggregates_lines_on_same_budget_line(client, pm):
    """Two $60k lines on a $100k budget must be enforced together, not one at a time."""
    project = _stop_project(client, pm, budget=100000)
    po = _manual_po(client, pm, project, [60000, 60000])
    resp = client.post(f"/api/v1/purchase-orders/{po['id']}/submit", headers=pm)
    assert resp.status_code == 422, resp.text
    assert "STOP" in resp.text


def test_pending_pos_reserve_budget_headroom(client, pm):
    """A second PO must see the first one's pending amount, not empty headroom."""
    project = _stop_project(client, pm, budget=100000)
    po1 = _manual_po(client, pm, project, [80000])
    resp = client.post(f"/api/v1/purchase-orders/{po1['id']}/submit", headers=pm)
    assert resp.status_code == 200, resp.text  # 80k of 100k: fine

    po2 = _manual_po(client, pm, project, [80000])
    resp = client.post(f"/api/v1/purchase-orders/{po2['id']}/submit", headers=pm)
    assert resp.status_code == 422, resp.text  # 80k pending + 80k = 160k > 100k


def test_sco_buyout_does_not_double_count_its_sco(client, pm):
    """A PO replacing its source SCO must not be blocked by that SCO's own commitment."""
    project = _stop_project(client, pm, budget=50000)
    sco = make_sco(client, pm, project, 40000)
    client.post(f"/api/v1/change-orders/{sco['id']}/transition", headers=pm,
                json={"action": "submit_for_approval"})
    step = client.get(f"/api/v1/change-orders/{sco['id']}/approvals", headers=pm).json()[0]
    assert client.post(f"/api/v1/approvals/{step['id']}/decide", headers=pm,
                       json={"approve": True}).json()["entity_status"] == "APPROVED"

    po = client.post(f"/api/v1/projects/{project['id']}/purchase-orders", headers=pm,
                     json={"vendor_id": project["vendor_id"],
                           "source_change_order_id": sco["id"]}).json()
    # Without the offset the projection would be 40k (SCO) + 40k (PO) = 80k > 50k STOP.
    resp = client.post(f"/api/v1/purchase-orders/{po['id']}/submit", headers=pm)
    assert resp.status_code == 200, resp.text
    assert resp.json()["budget_warnings"] == []


def test_sco_can_only_be_bought_out_once(client, pm):
    project = _stop_project(client, pm, budget=100000)
    sco = make_sco(client, pm, project, 20000)
    client.post(f"/api/v1/change-orders/{sco['id']}/transition", headers=pm,
                json={"action": "submit_for_approval"})
    step = client.get(f"/api/v1/change-orders/{sco['id']}/approvals", headers=pm).json()[0]
    client.post(f"/api/v1/approvals/{step['id']}/decide", headers=pm, json={"approve": True})

    first = client.post(f"/api/v1/projects/{project['id']}/purchase-orders", headers=pm,
                        json={"vendor_id": project["vendor_id"],
                              "source_change_order_id": sco["id"]})
    assert first.status_code == 201, first.text
    second = client.post(f"/api/v1/projects/{project['id']}/purchase-orders", headers=pm,
                         json={"vendor_id": project["vendor_id"],
                               "source_change_order_id": sco["id"]})
    assert second.status_code == 409
    assert "already bought out" in second.text


def test_audit_actor_tampering_is_detected(client, pm, project):
    """Rewriting WHO acted must break the chain, not just what was done."""
    from app.db.session import engine

    if engine.dialect.name == "postgresql":
        pytest.skip("Postgres blocks the raw UPDATE via trigger (covered elsewhere)")

    assert client.get("/api/v1/audit/verify", headers=pm).json()["valid"] is True
    with engine.connect() as conn:
        row = conn.execute(text(
            "SELECT id, actor_id FROM audit_events WHERE actor_id IS NOT NULL "
            "ORDER BY id LIMIT 1"
        )).first()
        conn.execute(text("UPDATE audit_events SET actor_id=999999 WHERE id=:id"),
                     {"id": row.id})
        conn.commit()
    verdict = client.get("/api/v1/audit/verify", headers=pm).json()
    assert verdict["valid"] is False and verdict["first_broken_event_id"] == row.id
    with engine.connect() as conn:  # restore for later tests
        conn.execute(text("UPDATE audit_events SET actor_id=:a WHERE id=:id"),
                     {"a": row.actor_id, "id": row.id})
        conn.commit()
    assert client.get("/api/v1/audit/verify", headers=pm).json()["valid"] is True


def test_pending_approvals_kpi_is_project_scoped(client, pm, project):
    """Project B's dashboard must not count project A's pending approvals."""
    sco = make_sco(client, pm, project, 10000)
    client.post(f"/api/v1/change-orders/{sco['id']}/transition", headers=pm,
                json={"action": "submit_for_approval"})
    kpis_a = client.get(f"/api/v1/projects/{project['id']}/kpis", headers=pm).json()
    assert kpis_a["pending_approvals"] >= 1

    other = _stop_project(client, pm, budget=10000)
    kpis_b = client.get(f"/api/v1/projects/{other['id']}/kpis", headers=pm).json()
    assert kpis_b["pending_approvals"] == 0
