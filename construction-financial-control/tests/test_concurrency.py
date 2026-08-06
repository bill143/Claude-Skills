"""Race-condition coverage: concurrent decisions, submissions, conversions.

The compare-and-swap status guards must let exactly one writer win; the loser
gets a clean 409/422, never a double-applied financial effect.
"""
from concurrent.futures import ThreadPoolExecutor

from tests.conftest import make_sco


def _race(fn_a, fn_b):
    with ThreadPoolExecutor(max_workers=2) as pool:
        fut_a, fut_b = pool.submit(fn_a), pool.submit(fn_b)
        return fut_a.result(timeout=60), fut_b.result(timeout=60)


def test_concurrent_approval_decisions(client, pm, project):
    sco = make_sco(client, pm, project, 10000)  # single PM step
    client.post(f"/api/v1/change-orders/{sco['id']}/transition", headers=pm,
                json={"action": "submit_for_approval"})
    step = client.get(f"/api/v1/change-orders/{sco['id']}/approvals", headers=pm).json()[0]

    def decide():
        return client.post(f"/api/v1/approvals/{step['id']}/decide", headers=pm,
                           json={"approve": True})

    resp_a, resp_b = _race(decide, decide)
    statuses = sorted([resp_a.status_code, resp_b.status_code])
    assert statuses == [200, 409], (resp_a.text, resp_b.text)

    # Effect applied exactly once: SCO approved, one decided step, 20k not 40k... (10k once).
    assert client.get(f"/api/v1/change-orders/{sco['id']}",
                      headers=pm).json()["status"] == "APPROVED"
    totals = client.get(f"/api/v1/projects/{project['id']}/forecast", headers=pm).json()["totals"]
    assert totals["committed"] == 10000.0


def test_concurrent_po_submit(client, pm, project):
    resp = client.post(f"/api/v1/projects/{project['id']}/purchase-orders", headers=pm,
                       json={"vendor_id": project["vendor_id"],
                             "lines": [{"budget_line_id": project["lines"]["05-100"],
                                        "description": "Steel", "quantity": 1,
                                        "unit_cost": 50000}]})
    po = resp.json()

    def submit():
        return client.post(f"/api/v1/purchase-orders/{po['id']}/submit", headers=pm)

    resp_a, resp_b = _race(submit, submit)
    statuses = sorted([resp_a.status_code, resp_b.status_code])
    assert statuses[0] == 200 and statuses[1] in (409, 422), (resp_a.text, resp_b.text)

    # Exactly one approval chain was built (PM step only for 50k PO).
    steps = client.get(f"/api/v1/purchase-orders/{po['id']}/approvals", headers=pm).json()
    assert len(steps) == 1


def test_concurrent_pco_convert(client, pm, project):
    resp = client.post(f"/api/v1/projects/{project['id']}/change-orders", headers=pm,
                       json={"co_type": "PCO", "title": "Race PCO",
                             "lines": [{"budget_line_id": project["lines"]["03-300"],
                                        "description": "work", "quantity": 1,
                                        "unit_cost": 30000}]})
    pco = resp.json()
    for action in ("send_to_pricing", "submit"):
        client.post(f"/api/v1/change-orders/{pco['id']}/transition", headers=pm,
                    json={"action": action})

    def convert():
        return client.post(f"/api/v1/change-orders/{pco['id']}/convert", headers=pm,
                           json={"targets": ["SCO"], "vendor_id": project["vendor_id"]})

    resp_a, resp_b = _race(convert, convert)
    statuses = sorted([resp_a.status_code, resp_b.status_code])
    assert statuses[0] == 200 and statuses[1] in (409, 422), (resp_a.text, resp_b.text)

    # Exactly one SCO spawned from the PCO.
    scos = client.get(f"/api/v1/projects/{project['id']}/change-orders", headers=pm,
                      params={"co_type": "SCO"}).json()
    from_pco = [c for c in scos if c["origin_pco_id"] == pco["id"]]
    assert len(from_pco) == 1
