"""Platform hardening: health probes, RBAC, config safety, rate limiter, migrations."""
import os
import subprocess
import sys
import tempfile

import pytest

from tests.conftest import PROJECT_ROOT


def test_liveness_and_readiness(client):
    assert client.get("/health/live").json()["status"] == "alive"
    ready = client.get("/health/ready")
    assert ready.status_code == 200
    assert ready.json()["checks"]["database"] == "ok"


def test_request_id_header_present(client):
    resp = client.get("/health/live", headers={"X-Request-ID": "test-corr-123"})
    assert resp.headers["X-Request-ID"] == "test-corr-123"
    resp = client.get("/health/live")
    assert len(resp.headers["X-Request-ID"]) == 32  # generated uuid4 hex


def test_unauthenticated_rejected(client, project):
    assert client.get("/api/v1/projects").status_code == 401
    assert client.post(f"/api/v1/projects/{project['id']}/change-orders",
                       json={"co_type": "PCO", "title": "x"}).status_code == 401


def test_viewer_cannot_mutate(client, viewer, project):
    resp = client.post(f"/api/v1/projects/{project['id']}/change-orders", headers=viewer,
                       json={"co_type": "PCO", "title": "nope", "lines": []})
    assert resp.status_code == 403
    resp = client.post(f"/api/v1/projects/{project['id']}/budget-lines", headers=viewer,
                       json={"cost_code": "99-999", "description": "x",
                             "original_budget": 1})
    assert resp.status_code == 403


def test_money_rejects_bad_precision(client, pm, project):
    resp = client.post(f"/api/v1/projects/{project['id']}/budget-lines", headers=pm,
                       json={"cost_code": "98-000", "description": "x",
                             "original_budget": 100.123})  # 3 decimal places
    assert resp.status_code == 422


def test_prod_config_refuses_insecure_defaults():
    from pydantic import ValidationError

    from app.core.config import Settings

    with pytest.raises(ValidationError, match="SECRET_KEY"):
        Settings(ENVIRONMENT="prod", _env_file=None)
    # Secure prod config is accepted.
    ok = Settings(ENVIRONMENT="prod", SECRET_KEY="x" * 40,
                  CORS_ORIGINS="https://app.example.com",
                  DATABASE_URL="postgresql+psycopg2://u:p@db/cfcs", _env_file=None)
    assert ok.AUTO_CREATE_TABLES is False


def test_rate_limiter_unit():
    from app.core.rate_limit import RateLimiter

    rl = RateLimiter()
    assert all(rl.allow("k", 3) for _ in range(3))
    assert rl.allow("k", 3) is False
    assert rl.allow("other", 3) is True


def test_alembic_migrations_run_clean():
    """alembic upgrade head must build the full schema on an empty database."""
    db_path = os.path.join(tempfile.mkdtemp(), "alembic-check.db")
    env = {**os.environ, "DATABASE_URL": f"sqlite:///{db_path}"}
    result = subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        cwd=PROJECT_ROOT, env=env, capture_output=True, text=True, timeout=120,
    )
    assert result.returncode == 0, result.stderr
    import sqlite3

    tables = {r[0] for r in sqlite3.connect(db_path).execute(
        "SELECT name FROM sqlite_master WHERE type='table'"
    )}
    assert {"projects", "budget_lines", "change_orders", "purchase_orders",
            "approval_rules", "approval_requests", "audit_events",
            "idempotency_records", "alembic_version"} <= tables
