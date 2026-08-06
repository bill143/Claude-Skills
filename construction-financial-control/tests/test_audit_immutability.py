"""Audit ledger: ORM mutation refused; raw tampering detected by verify-chain."""
import pytest
from sqlalchemy import text


def test_orm_update_and_delete_refused(client, pm, project):
    from app.db.session import SessionLocal
    from app.models.audit import AuditEvent
    from app.services.audit_service import AuditImmutabilityError

    db = SessionLocal()
    try:
        event = db.query(AuditEvent).first()
        assert event is not None
        event.action = "tampered"
        with pytest.raises(AuditImmutabilityError):
            db.commit()
        db.rollback()

        event = db.query(AuditEvent).first()
        db.delete(event)
        with pytest.raises(AuditImmutabilityError):
            db.commit()
        db.rollback()
    finally:
        db.close()


def test_verify_chain_detects_raw_sql_tampering(client, pm, project):
    """Bypass the ORM guard with raw SQL.

    PostgreSQL (with migration 0002 applied): the trigger must BLOCK the raw
    UPDATE outright. SQLite (no trigger): the update lands, and the hash chain
    must detect it via /audit/verify.
    """
    from sqlalchemy.exc import DBAPIError

    from app.db.session import engine

    assert client.get("/api/v1/audit/verify", headers=pm).json()["valid"] is True

    if engine.dialect.name == "postgresql":
        with pytest.raises(DBAPIError, match="append-only"):
            with engine.connect() as conn:
                conn.execute(text("UPDATE audit_events SET action='forged' "
                                  "WHERE id=(SELECT min(id) FROM audit_events)"))
                conn.commit()
        assert client.get("/api/v1/audit/verify", headers=pm).json()["valid"] is True
        return

    with engine.connect() as conn:
        row = conn.execute(text(
            "SELECT id, action FROM audit_events ORDER BY id LIMIT 1"
        )).first()
        original_action = row.action
        conn.execute(text("UPDATE audit_events SET action='forged' WHERE id=:id"),
                     {"id": row.id})
        conn.commit()

    verdict = client.get("/api/v1/audit/verify", headers=pm).json()
    assert verdict["valid"] is False
    assert verdict["first_broken_event_id"] == row.id

    # Restore so later tests see an intact chain.
    with engine.connect() as conn:
        conn.execute(text("UPDATE audit_events SET action=:a WHERE id=:id"),
                     {"a": original_action, "id": row.id})
        conn.commit()
    assert client.get("/api/v1/audit/verify", headers=pm).json()["valid"] is True
