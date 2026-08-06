"""Rejection auto-closes the chain; revise reopens the document."""
from tests.conftest import make_sco


def test_reject_then_revise_then_approve(client, pm, project):
    sco = make_sco(client, pm, project, 20000)

    resp = client.post(f"/api/v1/change-orders/{sco['id']}/transition", headers=pm,
                       json={"action": "submit_for_approval"})
    assert resp.status_code == 200 and resp.json()["status"] == "PENDING_APPROVAL"

    steps = client.get(f"/api/v1/change-orders/{sco['id']}/approvals", headers=pm).json()
    assert len(steps) == 1  # 20k < 50k -> PM only
    resp = client.post(f"/api/v1/approvals/{steps[0]['id']}/decide", headers=pm,
                       json={"approve": False, "comment": "price too high"})
    assert resp.json() == {"chain_complete": True, "entity_status": "REJECTED"}

    # No dangling PENDING steps after rejection.
    steps = client.get(f"/api/v1/change-orders/{sco['id']}/approvals", headers=pm).json()
    assert all(s["status"] != "PENDING" for s in steps)

    # A rejected SCO never counts as a commitment.
    totals = client.get(f"/api/v1/projects/{project['id']}/forecast", headers=pm).json()["totals"]
    assert totals["committed"] == 0.0

    # Revise -> DRAFT -> resubmit -> approve.
    resp = client.post(f"/api/v1/change-orders/{sco['id']}/transition", headers=pm,
                       json={"action": "revise"})
    assert resp.json()["status"] == "DRAFT"
    resp = client.post(f"/api/v1/change-orders/{sco['id']}/transition", headers=pm,
                       json={"action": "submit_for_approval"})
    assert resp.json()["status"] == "PENDING_APPROVAL"
    pending = [s for s in client.get(f"/api/v1/change-orders/{sco['id']}/approvals",
                                     headers=pm).json() if s["status"] == "PENDING"]
    assert len(pending) == 1
    resp = client.post(f"/api/v1/approvals/{pending[0]['id']}/decide", headers=pm,
                       json={"approve": True})
    assert resp.json()["entity_status"] == "APPROVED"
    totals = client.get(f"/api/v1/projects/{project['id']}/forecast", headers=pm).json()["totals"]
    assert totals["committed"] == 20000.0


def test_decided_step_cannot_be_redecided(client, pm, project):
    sco = make_sco(client, pm, project, 10000)
    client.post(f"/api/v1/change-orders/{sco['id']}/transition", headers=pm,
                json={"action": "submit_for_approval"})
    step = client.get(f"/api/v1/change-orders/{sco['id']}/approvals", headers=pm).json()[0]
    assert client.post(f"/api/v1/approvals/{step['id']}/decide", headers=pm,
                       json={"approve": True}).status_code == 200
    assert client.post(f"/api/v1/approvals/{step['id']}/decide", headers=pm,
                       json={"approve": True}).status_code == 409
