from datetime import date, datetime, timezone
from decimal import Decimal

from sqlalchemy import Date, DateTime, Enum, ForeignKey, Numeric, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base_class import Base
from app.models.enums import PurchaseOrderStatus


def _enum(e, length=32):
    return Enum(e, native_enum=False, length=length, values_callable=lambda x: [m.value for m in x])


class PurchaseOrder(Base):
    """Commitment document. APPROVED/CLOSED POs count toward committed cost.

    A PO may be sourced from an approved SCO (source_change_order_id), in which
    case the SCO stops counting as a commitment itself to avoid double counting.
    """

    __tablename__ = "purchase_orders"
    __table_args__ = (UniqueConstraint("project_id", "number", name="uq_po_project_number"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), nullable=False, index=True)
    number: Mapped[str] = mapped_column(String(50), nullable=False)
    vendor_id: Mapped[int] = mapped_column(ForeignKey("vendors.id"), nullable=False)
    status: Mapped[PurchaseOrderStatus] = mapped_column(
        _enum(PurchaseOrderStatus), nullable=False, default=PurchaseOrderStatus.DRAFT, index=True
    )
    source_change_order_id: Mapped[int | None] = mapped_column(ForeignKey("change_orders.id"))
    issued_date: Mapped[date | None] = mapped_column(Date)
    notes: Mapped[str | None] = mapped_column(Text)
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
        "PurchaseOrderLine", back_populates="purchase_order", cascade="all, delete-orphan", lazy="selectin"
    )
    vendor = relationship("Vendor")
    source_change_order = relationship("ChangeOrder")

    @property
    def total_amount(self) -> Decimal:
        return sum((line.amount for line in self.lines), Decimal("0"))


class PurchaseOrderLine(Base):
    __tablename__ = "purchase_order_lines"

    id: Mapped[int] = mapped_column(primary_key=True)
    purchase_order_id: Mapped[int] = mapped_column(
        ForeignKey("purchase_orders.id"), nullable=False, index=True
    )
    budget_line_id: Mapped[int] = mapped_column(ForeignKey("budget_lines.id"), nullable=False)
    description: Mapped[str] = mapped_column(String(255), nullable=False)
    quantity: Mapped[Decimal] = mapped_column(Numeric(14, 3), nullable=False, default=Decimal("1"))
    unit_cost: Mapped[Decimal] = mapped_column(Numeric(16, 2), nullable=False, default=Decimal("0"))
    amount: Mapped[Decimal] = mapped_column(Numeric(16, 2), nullable=False, default=Decimal("0"))

    purchase_order = relationship("PurchaseOrder", back_populates="lines")
    budget_line = relationship("BudgetLine")
