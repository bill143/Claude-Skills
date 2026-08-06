"""Idempotency-Key handling for approval / submit / transition endpoints.

Contract (Stripe-style): clients send a unique `Idempotency-Key` header per
logical operation. Retries with the same key + same payload replay the stored
response without re-executing side effects; the same key with a different
payload is a 422; a concurrent duplicate while the first attempt is still
in flight is a 409.
"""
import hashlib
import json
from collections.abc import Callable

from fastapi import HTTPException
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.idempotency import IdempotencyRecord
from app.models.user import User

MAX_KEY_LENGTH = 128


def _hash_payload(payload) -> str:
    canonical = json.dumps(jsonable_encoder(payload), sort_keys=True, separators=(",", ":"),
                           default=str)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def run_idempotent(
    db: Session,
    *,
    key: str | None,
    user: User,
    endpoint: str,
    payload,
    fn: Callable[[], object],
    status_code: int = 200,
):
    """Execute fn() at most once per (key, endpoint, user); replay on retry.

    Without a key the operation runs normally (the header is opt-in, but the
    Streamlit client and any integration SHOULD send one for money-moving calls).
    """
    if key is None:
        return fn()
    if not key or len(key) > MAX_KEY_LENGTH:
        raise HTTPException(status_code=422, detail="Invalid Idempotency-Key header")

    request_hash = _hash_payload(payload)
    existing = db.execute(
        select(IdempotencyRecord).where(
            IdempotencyRecord.key == key,
            IdempotencyRecord.endpoint == endpoint,
            IdempotencyRecord.user_id == user.id,
        )
    ).scalar_one_or_none()
    if existing is None:
        record = IdempotencyRecord(
            key=key, endpoint=endpoint, user_id=user.id, request_hash=request_hash
        )
        db.add(record)
        try:
            db.commit()
        except IntegrityError:
            # Lost the insert race to a concurrent duplicate.
            db.rollback()
            existing = db.execute(
                select(IdempotencyRecord).where(
                    IdempotencyRecord.key == key,
                    IdempotencyRecord.endpoint == endpoint,
                    IdempotencyRecord.user_id == user.id,
                )
            ).scalar_one()

    if existing is not None:
        if existing.request_hash != request_hash:
            raise HTTPException(
                status_code=422,
                detail="Idempotency-Key was already used with a different request payload",
            )
        if existing.response_status is None:
            raise HTTPException(
                status_code=409,
                detail="A request with this Idempotency-Key is already in flight",
            )
        return JSONResponse(status_code=existing.response_status, content=existing.response_body)

    try:
        result = fn()
    except HTTPException:
        # Domain rejection: release the key so the client may retry after fixing.
        fresh = db.execute(
            select(IdempotencyRecord).where(
                IdempotencyRecord.key == key,
                IdempotencyRecord.endpoint == endpoint,
                IdempotencyRecord.user_id == user.id,
            )
        ).scalar_one_or_none()
        if fresh is not None and fresh.response_status is None:
            db.delete(fresh)
            db.commit()
        raise

    body = jsonable_encoder(result)
    fresh = db.execute(
        select(IdempotencyRecord).where(
            IdempotencyRecord.key == key,
            IdempotencyRecord.endpoint == endpoint,
            IdempotencyRecord.user_id == user.id,
        )
    ).scalar_one()
    fresh.response_status = status_code
    fresh.response_body = body
    db.commit()
    return result
