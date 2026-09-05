"""WBS tree, CSI library, budget import, manual ETC, corrected forecast math."""
import io
from datetime import date


def _line(client, pm, project_id, code, amount, description=None, category="SUBCONTRACT"):
    payload = {"cost_code": code, "category": category, "original_budget": amount}
    if description is not None:
        payload["description"] = description
    resp = client.post(f"/api/v1/projects/{project_id}/budget-lines", headers=pm, json=payload)
    assert resp.status_code == 201, resp.text
    return resp.json()


def test_actuals_draw_down_budget_not_stack_on_it(client, pm, project):
    """The bug from the field: $40k actuals with $0 committed must NOT inflate EAC."""
    line = _line(client, pm, project["id"], "31 23 00", 100000, "Excavation")
    assert client.post(f"/api/v1/budget-lines/{line['id']}/costs", headers=pm,
                       json={"entry_date": str(date.today()), "amount": 40000,
                             "description": "Draw"}).status_code == 201
    forecast = client.get(f"/api/v1/projects/{project['id']}/forecast", headers=pm).json()
    row = next(r for r in forecast["lines"] if r["id"] == line["id"])
    assert row["eac"] == 100000.0  # budget, not budget + actuals
    assert row["etc"] == 60000.0
    assert row["vac"] == 0.0
    # Overrun case: actuals beyond budget push EAC up.
    client.post(f"/api/v1/budget-lines/{line['id']}/costs", headers=pm,
                json={"entry_date": str(date.today()), "amount": 75000})
    forecast = client.get(f"/api/v1/projects/{project['id']}/forecast", headers=pm).json()
    row = next(r for r in forecast["lines"] if r["id"] == line["id"])
    assert row["eac"] == 115000.0 and row["vac"] == -15000.0


def test_manual_etc_override_and_clear(client, pm, project):
    line = _line(client, pm, project["id"], "09 29 00", 80000, "Gypsum Board")
    client.post(f"/api/v1/budget-lines/{line['id']}/costs", headers=pm,
                json={"entry_date": str(date.today()), "amount": 30000})
    resp = client.patch(f"/api/v1/budget-lines/{line['id']}", headers=pm,
                        json={"manual_etc": 20000})
    assert resp.status_code == 200 and resp.json()["manual_etc"] == 20000.0
    forecast = client.get(f"/api/v1/projects/{project['id']}/forecast", headers=pm).json()
    row = next(r for r in forecast["lines"] if r["id"] == line["id"])
    assert row["method"] == "MANUAL"
    assert row["eac"] == 50000.0 and row["etc"] == 20000.0 and row["vac"] == 30000.0
    resp = client.patch(f"/api/v1/budget-lines/{line['id']}", headers=pm,
                        json={"clear_manual_etc": True})
    assert resp.json()["manual_etc"] is None
    forecast = client.get(f"/api/v1/projects/{project['id']}/forecast", headers=pm).json()
    row = next(r for r in forecast["lines"] if r["id"] == line["id"])
    assert row["method"] == "REMAINING_BUDGET" and row["eac"] == 80000.0


def test_code_normalization_and_library_autotitle(client, pm, project):
    line = _line(client, pm, project["id"], "033000", 5000)  # no description given
    assert line["cost_code"] == "03 30 00"
    assert line["description"] == "Cast-in-Place Concrete"  # from the CSI library


def test_cost_code_search_and_divisions(client, pm):
    rows = client.get("/api/v1/cost-codes", headers=pm,
                      params={"q": "concrete", "division": "03"}).json()
    assert any(r["code"] == "03 30 00" for r in rows)
    divisions = client.get("/api/v1/cost-codes/divisions", headers=pm).json()
    assert len(divisions) == 25
    div03 = next(d for d in divisions if d["division"] == "03")
    assert div03["title"] == "Concrete" and div03["code_count"] > 50


def test_wbs_tree_rollups(client, pm, project):
    _line(client, pm, project["id"], "03 30 00", 100000)
    _line(client, pm, project["id"], "03 35 00", 50000)
    _line(client, pm, project["id"], "05 12 00", 75000)
    wbs = client.get(f"/api/v1/projects/{project['id']}/wbs", headers=pm).json()
    # project fixture pre-creates 03-300 and 05-100 style lines (divisions 03/05)
    divisions = {d["division"]: d for d in wbs["divisions"]}
    assert set(divisions) == {"03", "05"}
    assert divisions["03"]["title"] == "Concrete"
    assert divisions["05"]["title"] == "Metals"
    # Division rollup = its own lines incl. the fixture's (1,000,000 + 750,000)
    assert divisions["03"]["rollup"]["original_budget"] == 1150000.0
    assert divisions["05"]["rollup"]["original_budget"] == 825000.0
    assert wbs["totals"]["original_budget"] == 1975000.0
    section_codes = [s["code"] for s in divisions["03"]["sections"]]
    assert "03 30 00" in section_codes and "03 35 00" in section_codes


def test_import_csv_preview_and_commit(client, pm, project):
    csv_bytes = (
        b"Cost Code,Description,Budget\n"
        b'"03 31 00",Structural Concrete,"$250,000.00"\n'
        b"051200,,125000\n"          # description auto-fills from library
        b"03 31 00,dupe in file,50000\n"  # merges into the first row
        b"26 05 00,Common Work Results for Electrical,90000\n"
    )
    preview = client.post(
        f"/api/v1/projects/{project['id']}/budget-lines/import", headers=pm,
        params={"mode": "preview"},
        files={"file": ("budget.csv", csv_bytes, "text/csv")},
    )
    assert preview.status_code == 200, preview.text
    body = preview.json()
    assert body["rows_parsed"] == 3 and body["rows_invalid"] == 0
    merged = next(r for r in body["rows"] if r["code"] == "03 31 00")
    assert merged["amount"] == 300000.0 and merged["merged_rows"] == 2
    steel = next(r for r in body["rows"] if r["code"] == "05 12 00")
    assert steel["description"] == "Structural Steel Framing" and steel["in_library"]
    assert body["total_amount_new"] == 515000.0

    commit = client.post(
        f"/api/v1/projects/{project['id']}/budget-lines/import", headers=pm,
        params={"mode": "commit"},
        files={"file": ("budget.csv", csv_bytes, "text/csv")},
    )
    assert commit.status_code == 200 and commit.json()["created"] == 3

    # Re-import: duplicates skipped by default, updated when asked.
    again = client.post(
        f"/api/v1/projects/{project['id']}/budget-lines/import", headers=pm,
        params={"mode": "commit", "on_duplicate": "skip"},
        files={"file": ("budget.csv", csv_bytes, "text/csv")},
    ).json()
    assert again["created"] == 0 and again["skipped"] == 3
    lines = client.get(f"/api/v1/projects/{project['id']}/budget-lines", headers=pm).json()
    assert sum(1 for line in lines if line["cost_code"] == "03 31 00") == 1


def test_import_xlsx(client, pm, project):
    import openpyxl

    workbook = openpyxl.Workbook()
    ws = workbook.active
    ws.append(["CSI", "Title", "Amount"])
    ws.append(["07 21 00", "Thermal Insulation", 45000])
    ws.append(["08 11 00", "Metal Doors and Frames", 62000])
    buffer = io.BytesIO()
    workbook.save(buffer)
    resp = client.post(
        f"/api/v1/projects/{project['id']}/budget-lines/import", headers=pm,
        params={"mode": "commit"},
        files={"file": ("budget.xlsx", buffer.getvalue(),
                        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["created"] == 2


def test_import_invalid_rows_block_commit(client, pm, project):
    csv_bytes = b"Code,Amount\n03 30 00,not-a-number\n"
    preview = client.post(
        f"/api/v1/projects/{project['id']}/budget-lines/import", headers=pm,
        params={"mode": "preview"}, files={"file": ("bad.csv", csv_bytes, "text/csv")},
    ).json()
    assert preview["rows_invalid"] == 1
    commit = client.post(
        f"/api/v1/projects/{project['id']}/budget-lines/import", headers=pm,
        params={"mode": "commit"}, files={"file": ("bad.csv", csv_bytes, "text/csv")},
    )
    assert commit.status_code == 422


def test_budget_line_detail_drilldown(client, pm, project):
    """Every number on a line traces to its documents."""
    line_id = project["lines"]["03-300"]
    client.post(f"/api/v1/budget-lines/{line_id}/costs", headers=pm,
                json={"entry_date": str(date.today()), "amount": 12000,
                      "description": "Pump truck invoice"})
    detail = client.get(f"/api/v1/budget-lines/{line_id}/detail", headers=pm).json()
    assert detail["metrics"]["actual"] == 12000.0
    assert detail["cost_entries"][0]["description"] == "Pump truck invoice"
    assert detail["change_orders"] == [] and detail["purchase_orders"] == []


def test_project_create_and_patch(client, pm):
    resp = client.post("/api/v1/projects", headers=pm,
                       json={"code": "PATCH-1", "name": "Original Name",
                             "original_contract_value": 1000000})
    project_id = resp.json()["id"]
    resp = client.patch(f"/api/v1/projects/{project_id}", headers=pm,
                        json={"name": "Renamed Tower", "original_contract_value": 2500000,
                              "budget_control": "STOP"})
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["name"] == "Renamed Tower"
    assert body["original_contract_value"] == 2500000.0
    assert body["budget_control"] == "STOP"
    assert client.patch(f"/api/v1/projects/{project_id}", headers=pm,
                        json={}).status_code == 422
