from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, Numeric, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base_class import Base
from app.models.enums import ChangeOrderStatus, ChangeOrderType


def _enum(e, length=32):
    return Enum(e, native_enum=False, length=length, values_callable=lambda x: [m.value for m in x])


class ChangeOrder(Base):
    """Unified change-order document: PCO, OCO, and SCO share one table.

    Lifecycle:
      PCO: DRAFT -> PRICING -> SUBMITTED -> CONVERTED (spawns OCO/SCO) | VOID
      OCO/SCO: DRAFT -> PENDING_APPROVAL -> APPROVED | REJECTED (-> DRAFT via revise)
    Converted documents keep `origin_pco_id` so the full chain is traceable.
    """

    __tablename__ = "change_orders"
    __table_args__ = (UniqueConstraint("project_id", "number", name="uq_co_project_number"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), nullable=False, index=True)
    number: Mapped[str] = mapped_column(String(50), nullable=False)
    co_type: Mapped[ChangeOrderType] = mapped_column(_enum(ChangeOrderType), nullable=False)
    status: Mapped[ChangeOrderStatus] = mapped_column(
        _enum(ChangeOrderStatus), nullable=False, default=ChangeOrderStatus.DRAFT, index=True
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    vendor_id: Mapped[int | None] = mapped_column(ForeignKey("vendors.id"))  # SCO only
    origin_pco_id: Mapped[int | None] = mapped_column(ForeignKey("change_orders.id"))
    schedule_impact_days: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    lines = relationship(
        "ChangeOrderLine", back_populates="change_order", cascade="all, delete-orphan", lazy="selectin"
    )
    vendor = relationship("Vendor")
    origin_pco = relationship("ChangeOrder", remote_side=[id])

    @property
    def total_amount(self) -> Decimal:
        return sum((line.amount for line in self.lines), Decimal("0"))


class ChangeOrderLine(Base):
    __tablename__ = "change_order_lines"

    id: Mapped[int] = mapped_column(primary_key=True)
    change_order_id: Mapped[int] = mapped_column(
        ForeignKey("change_orders.id"), nullable=False, index=True
    )
    budget_line_id: Mapped[int] = mapped_column(ForeignKey("budget_lines.id"), nullable=False)
    description: Mapped[str] = mapped_column(String(255), nullable=False)
    quantity: Mapped[Decimal] = mapped_column(Numeric(14, 3), nullable=False, default=Decimal("1"))
    unit_cost: Mapped[Decimal] = mapped_column(Numeric(16, 2), nullable=False, default=Decimal("0"))
    amount: Mapped[Decimal] = mapped_column(Numeric(16, 2), nullable=False, default=Decimal("0"))

    change_order = relationship("ChangeOrder", back_populates="lines")
    budget_line = relationship("BudgetLine")
