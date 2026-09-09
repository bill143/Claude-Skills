"""Idempotency-Key behavior on approval and submission endpoints."""
import uuid
from concurrent.futures import ThreadPoolExecutor

from tests.conftest import make_sco


def _audit_count(client, headers) -> int:
    return len(client.get("/api/v1/audit", headers=headers, params={"limit": 1000}).json())


def test_decide_replay_returns_stored_response(client, pm, project):
    sco = make_sco(client, pm, project, 10000)
    client.post(f"/api/v1/change-orders/{sco['id']}/transition", headers=pm,
                json={"action": "submit_for_approval"})
    step = client.get(f"/api/v1/change-orders/{sco['id']}/approvals", headers=pm).json()[0]

    key = uuid.uuid4().hex
    headers = {**pm, "Idempotency-Key": key}
    first = client.post(f"/api/v1/approvals/{step['id']}/decide", headers=headers,
                        json={"approve": True})
    assert first.status_code == 200, first.text
    count_after_first = _audit_count(client, pm)

    replay = client.post(f"/api/v1/approvals/{step['id']}/decide", headers=headers,
                         json={"approve": True})
    assert replay.status_code == 200
    assert replay.json() == first.json()
    # Replay produced no new side effects (no extra audit events).
    assert _audit_count(client, pm) == count_after_first


def test_key_reuse_with_different_payload_rejected(client, pm, project):
    sco = make_sco(client, pm, project, 10000)
    client.post(f"/api/v1/change-orders/{sco['id']}/transition", headers=pm,
                json={"action": "submit_for_approval"})
    step = client.get(f"/api/v1/change-orders/{sco['id']}/approvals", headers=pm).json()[0]

    key = uuid.uuid4().hex
    headers = {**pm, "Idempotency-Key": key}
    assert client.post(f"/api/v1/approvals/{step['id']}/decide", headers=headers,
                       json={"approve": True}).status_code == 200
    resp = client.post(f"/api/v1/approvals/{step['id']}/decide", headers=headers,
                       json={"approve": False})
    assert resp.status_code == 422
    assert "different request payload" in resp.text


def test_po_double_submit_with_same_key(client, pm, project):
    resp = client.post(f"/api/v1/projects/{project['id']}/purchase-orders", headers=pm,
                       json={"vendor_id": project["vendor_id"],
                             "lines": [{"budget_line_id": project["lines"]["03-300"],
                                        "description": "Concrete", "quantity": 1,
                                        "unit_cost": 40000}]})
    po = resp.json()
    key = uuid.uuid4().hex
    headers = {**pm, "Idempotency-Key": key}

    first = client.post(f"/api/v1/purchase-orders/{po['id']}/submit", headers=headers)
    replay = client.post(f"/api/v1/purchase-orders/{po['id']}/submit", headers=headers)
    assert first.status_code == 200 and replay.status_code == 200
    assert replay.json() == first.json()
    # Only one approval chain exists.
    steps = client.get(f"/api/v1/purchase-orders/{po['id']}/approvals", headers=pm).json()
    assert len(steps) == 1


def test_concurrent_duplicate_with_same_key(client, pm, project):
    sco = make_sco(client, pm, project, 10000)
    client.post(f"/api/v1/change-orders/{sco['id']}/transition", headers=pm,
                json={"action": "submit_for_approval"})
    step = client.get(f"/api/v1/change-orders/{sco['id']}/approvals", headers=pm).json()[0]
    key = uuid.uuid4().hex
    headers = {**pm, "Idempotency-Key": key}

    def decide():
        return client.post(f"/api/v1/approvals/{step['id']}/decide", headers=headers,
                           json={"approve": True})

    with ThreadPoolExecutor(max_workers=2) as pool:
        fut_a, fut_b = pool.submit(decide), pool.submit(decide)
        resp_a, resp_b = fut_a.result(timeout=60), fut_b.result(timeout=60)

    # One executes; the other replays (200) or reports in-flight (409).
    assert {resp_a.status_code, resp_b.status_code} <= {200, 409}
    assert 200 in (resp_a.status_code, resp_b.status_code)
    assert client.get(f"/api/v1/change-orders/{sco['id']}",
                      headers=pm).json()["status"] == "APPROVED"


def test_domain_rejection_releases_key(client, pm, project):
    """A 4xx from the domain logic must not burn the key forever."""
    sco = make_sco(client, pm, project, 10000)
    key = uuid.uuid4().hex
    headers = {**pm, "Idempotency-Key": key}
    # Invalid action while DRAFT -> 422; key is released.
    resp = client.post(f"/api/v1/change-orders/{sco['id']}/transition", headers=headers,
                       json={"action": "revise"})
    assert resp.status_code == 422
    # Same key now works for a valid request.
    resp = client.post(f"/api/v1/change-orders/{sco['id']}/transition", headers=headers,
                       json={"action": "submit_for_approval"})
    assert resp.status_code == 200, resp.text
