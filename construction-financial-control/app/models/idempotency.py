from datetime import UTC, datetime

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base_class import Base


class IdempotencyRecord(Base):
    """Replay guard for financially sensitive endpoints.

    A row is inserted (as in-flight, response_status NULL) BEFORE the guarded
    operation runs; the unique constraint makes concurrent duplicates lose the
    insert race, so the side effect can only execute once per
    (key, endpoint, user). The stored response is replayed on retry.
    """

    __tablename__ = "idempotency_records"
    __table_args__ = (
        UniqueConstraint("key", "endpoint", "user_id", name="uq_idem_key_endpoint_user"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    key: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    endpoint: Mapped[str] = mapped_column(String(200), nullable=False)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    request_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    response_status: Mapped[int | None] = mapped_column(Integer)
    response_body: Mapped[dict | None] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False
    )
