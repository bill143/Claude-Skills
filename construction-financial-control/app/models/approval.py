from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base_class import Base
from app.models.enums import ApprovalEntityType, ApprovalStatus, UserRole


def _enum(e, length=32):
    return Enum(e, native_enum=False, length=length, values_callable=lambda x: [m.value for m in x])


class ApprovalRule(Base):
    """Role + threshold approval matrix (OCA base_tier_validation pattern).

    A document of total amount X requires, in `sequence` order, one approval
    from every rule of its entity type whose threshold_amount <= X.
    """

    __tablename__ = "approval_rules"

    id: Mapped[int] = mapped_column(primary_key=True)
    entity_type: Mapped[ApprovalEntityType] = mapped_column(_enum(ApprovalEntityType), nullable=False)
    role: Mapped[UserRole] = mapped_column(_enum(UserRole), nullable=False)
    threshold_amount: Mapped[Decimal] = mapped_column(Numeric(16, 2), nullable=False, default=Decimal("0"))
    sequence: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    description: Mapped[str | None] = mapped_column(String(255))


class ApprovalRequest(Base):
    """One step of an in-flight approval chain for a specific document."""

    __tablename__ = "approval_requests"

    id: Mapped[int] = mapped_column(primary_key=True)
    entity_type: Mapped[ApprovalEntityType] = mapped_column(
        _enum(ApprovalEntityType), nullable=False, index=True
    )
    entity_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    required_role: Mapped[UserRole] = mapped_column(_enum(UserRole), nullable=False)
    status: Mapped[ApprovalStatus] = mapped_column(
        _enum(ApprovalStatus), nullable=False, default=ApprovalStatus.PENDING, index=True
    )
    approver_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    comment: Mapped[str | None] = mapped_column(String(500))
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False
    )

    approver = relationship("User")
