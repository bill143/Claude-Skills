"""Append-only, hash-chained audit ledger.

Pattern: Apache Fineract's command/audit journal (every state-changing command
is journaled with maker + payload) combined with a per-table hash chain so
tampering is detectable. Frappe's Version doctype inspired the JSON payload
diff style.
"""
import hashlib
import json
from datetime import UTC, datetime

from sqlalchemy import event, select, text
from sqlalchemy.orm import Session

from app.models.audit import AuditEvent
from app.models.user import User

GENESIS_HASH = "0" * 64


class AuditImmutabilityError(RuntimeError):
    pass


@event.listens_for(AuditEvent, "before_update")
def _forbid_update(mapper, connection, target):  # noqa: ANN001
    raise AuditImmutabilityError("audit_events is append-only: updates are forbidden")


@event.listens_for(AuditEvent, "before_delete")
def _forbid_delete(mapper, connection, target):  # noqa: ANN001
    raise AuditImmutabilityError("audit_events is append-only: deletes are forbidden")


def _canonical(payload: dict) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)


def _canonical_ts(created_at: datetime) -> str:
    """Timestamp form that survives the DB round-trip on any backend.

    SQLite drops tzinfo and Postgres may localize timestamptz on read, so
    normalize to naive UTC with fixed microsecond precision before hashing.
    """
    if created_at.tzinfo is not None:
        created_at = created_at.astimezone(UTC).replace(tzinfo=None)
    return created_at.isoformat(timespec="microseconds")


def _compute_hash(prev_hash: str, entity_type: str, entity_id: int, action: str,
                  actor_id: int | None, payload: dict, created_at: datetime) -> str:
    # actor_id is part of the hash: rewriting WHO did something is tampering
    # just as much as rewriting what was done.
    material = (f"{prev_hash}|{entity_type}|{entity_id}|{action}|{actor_id}|"
                f"{_canonical(payload)}|{_canonical_ts(created_at)}")
    return hashlib.sha256(material.encode("utf-8")).hexdigest()


def record(db: Session, *, actor: User | None, entity_type: str, entity_id: int,
           action: str, payload: dict | None = None) -> AuditEvent:
    """Append one event to the ledger. Flushes (does not commit) the session.

    Appends are serialized: concurrent transactions must not both read the
    same tail and fork the chain. On PostgreSQL a transaction-scoped advisory
    lock does this; SQLite's single-writer lock already serializes writers.
    """
    payload = payload or {}
    if db.get_bind().dialect.name == "postgresql":
        db.execute(text("SELECT pg_advisory_xact_lock(hashtext('audit_events_chain'))"))
    last = db.execute(select(AuditEvent).order_by(AuditEvent.id.desc()).limit(1)).scalar_one_or_none()
    prev_hash = last.hash if last else GENESIS_HASH
    created_at = datetime.now(UTC)
    actor_id = actor.id if actor else None
    event = AuditEvent(
        entity_type=entity_type,
        entity_id=entity_id,
        action=action,
        actor_id=actor_id,
        payload=payload,
        prev_hash=prev_hash,
        hash=_compute_hash(prev_hash, entity_type, entity_id, action, actor_id,
                           payload, created_at),
        created_at=created_at,
    )
    db.add(event)
    db.flush()
    return event


def verify_chain(db: Session) -> dict:
    """Recompute the whole chain; report first break if any."""
    events = db.execute(select(AuditEvent).order_by(AuditEvent.id.asc())).scalars().all()
    prev_hash = GENESIS_HASH
    for entry in events:
        if entry.prev_hash != prev_hash:
            return {"valid": False, "events": len(events), "first_broken_event_id": entry.id,
                    "reason": "prev_hash mismatch"}
        expected = _compute_hash(prev_hash, entry.entity_type, entry.entity_id,
                                 entry.action, entry.actor_id, entry.payload, entry.created_at)
        if entry.hash != expected:
            return {"valid": False, "events": len(events), "first_broken_event_id": entry.id,
                    "reason": "hash mismatch"}
        prev_hash = entry.hash
    return {"valid": True, "events": len(events), "first_broken_event_id": None, "reason": None}
