"""E2E: PCO -> convert -> SCO/OCO approval chains -> PO -> forecast update."""


def test_pco_to_forecast(client, pm, boss, project):
    project_id = project["id"]
    lines = project["lines"]

    # PCO with two lines: 60k + 15k = 75k
    resp = client.post(f"/api/v1/projects/{project_id}/change-orders", headers=pm,
                       json={"co_type": "PCO", "title": "Skylight", "schedule_impact_days": 5,
                             "lines": [
                                 {"budget_line_id": lines["03-300"], "description": "Deck mods",
                                  "quantity": 1, "unit_cost": 60000},
                                 {"budget_line_id": lines["05-100"], "description": "Framing",
                                  "quantity": 1, "unit_cost": 15000},
                             ]})
    assert resp.status_code == 201, resp.text
    pco = resp.json()
    assert pco["total_amount"] == 75000.0

    for action, expected in (("send_to_pricing", "PRICING"), ("submit", "SUBMITTED")):
        resp = client.post(f"/api/v1/change-orders/{pco['id']}/transition", headers=pm,
                           json={"action": action})
        assert resp.status_code == 200 and resp.json()["status"] == expected

    # Illegal transition rejected by the state table.
    resp = client.post(f"/api/v1/change-orders/{pco['id']}/transition", headers=pm,
                       json={"action": "send_to_pricing"})
    assert resp.status_code == 422

    resp = client.post(f"/api/v1/change-orders/{pco['id']}/convert", headers=pm,
                       json={"targets": ["OCO", "SCO"], "vendor_id": project["vendor_id"],
                             "oco_markup_pct": 0.10})
    assert resp.status_code == 200, resp.text
    created = {d["co_type"]: d for d in resp.json()}
    sco, oco = created["SCO"], created["OCO"]
    assert sco["total_amount"] == 75000.0 and oco["total_amount"] == 82500.0

    # SCO chain: PM then EXEC (75k >= 50k). Sequence + role enforcement.
    resp = client.post(f"/api/v1/change-orders/{sco['id']}/transition", headers=pm,
                       json={"action": "submit_for_approval"})
    assert resp.status_code == 200 and resp.json()["status"] == "PENDING_APPROVAL"
    steps = client.get(f"/api/v1/change-orders/{sco['id']}/approvals", headers=pm).json()
    assert [s["required_role"] for s in steps] == ["PROJECT_MANAGER", "EXECUTIVE"]
    assert client.post(f"/api/v1/approvals/{steps[1]['id']}/decide", headers=boss,
                       json={"approve": True}).status_code == 409
    assert client.post(f"/api/v1/approvals/{steps[0]['id']}/decide", headers=boss,
                       json={"approve": True}).status_code == 403
    assert client.post(f"/api/v1/approvals/{steps[0]['id']}/decide", headers=pm,
                       json={"approve": True}).json()["chain_complete"] is False
    resp = client.post(f"/api/v1/approvals/{steps[1]['id']}/decide", headers=boss,
                       json={"approve": True})
    assert resp.json() == {"chain_complete": True, "entity_status": "APPROVED"}

    totals = client.get(f"/api/v1/projects/{project_id}/forecast", headers=pm).json()["totals"]
    assert totals["committed"] == 75000.0

    # OCO approval revises budget + contract value.
    client.post(f"/api/v1/change-orders/{oco['id']}/transition", headers=pm,
                json={"action": "submit_for_approval"})
    steps = client.get(f"/api/v1/change-orders/{oco['id']}/approvals", headers=pm).json()
    for step, headers in zip(steps, (pm, boss), strict=True):
        assert client.post(f"/api/v1/approvals/{step['id']}/decide", headers=headers,
                           json={"approve": True}).status_code == 200
    totals = client.get(f"/api/v1/projects/{project_id}/forecast", headers=pm).json()["totals"]
    assert totals["approved_changes"] == 82500.0
    assert totals["current_budget"] == 1832500.0

    # PO from SCO supersedes the SCO commitment (no double counting).
    resp = client.post(f"/api/v1/projects/{project_id}/purchase-orders", headers=pm,
                       json={"vendor_id": project["vendor_id"],
                             "source_change_order_id": sco["id"]})
    assert resp.status_code == 201, resp.text
    po = resp.json()
    assert po["total_amount"] == 75000.0
    resp = client.post(f"/api/v1/purchase-orders/{po['id']}/submit", headers=pm)
    assert resp.status_code == 200 and resp.json()["approval_steps"] == 1
    step = client.get(f"/api/v1/purchase-orders/{po['id']}/approvals", headers=pm).json()[0]
    assert client.post(f"/api/v1/approvals/{step['id']}/decide", headers=pm,
                       json={"approve": True}).json()["entity_status"] == "APPROVED"
    totals = client.get(f"/api/v1/projects/{project_id}/forecast", headers=pm).json()["totals"]
    assert totals["committed"] == 75000.0

    # Actuals -> EAC/ETC (remaining-budget) and CPI method.
    from datetime import date
    assert client.post(f"/api/v1/budget-lines/{lines['03-300']}/costs", headers=pm,
                       json={"entry_date": str(date.today()), "amount": 30000,
                             "description": "Draw"}).status_code == 201
    forecast = client.get(f"/api/v1/projects/{project_id}/forecast", headers=pm).json()
    concrete = next(r for r in forecast["lines"] if r["cost_code"] == "03-300")
    assert concrete["current_budget"] == 1066000.0
    assert concrete["committed"] == 60000.0
    assert concrete["eac"] == 1066000.0 and concrete["etc"] == 1036000.0
    assert concrete["vac"] == 0.0

    cpi = client.get(f"/api/v1/projects/{project_id}/forecast", headers=pm,
                     params={"method": "CPI", "percent_complete": 0.5}).json()
    assert next(r for r in cpi["lines"] if r["cost_code"] == "03-300")["eac"] == 60000.0

    kpis = client.get(f"/api/v1/projects/{project_id}/kpis", headers=pm).json()
    assert kpis["contract_value"] == 5082500.0
    assert kpis["committed"] == 75000.0 and kpis["actual_to_date"] == 30000.0

    assert client.post(f"/api/v1/projects/{project_id}/forecast/snapshot",
                       headers=pm).status_code == 201
    verify = client.get("/api/v1/audit/verify", headers=pm).json()
    assert verify["valid"] is True
