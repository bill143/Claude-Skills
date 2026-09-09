from datetime import UTC, date, datetime
from decimal import Decimal

from sqlalchemy import Date, DateTime, Enum, ForeignKey, Numeric, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base_class import Base
from app.models.enums import CostCategory, ForecastMethod


def _enum(e, length=32):
    return Enum(e, native_enum=False, length=length, values_callable=lambda x: [m.value for m in x])


class BudgetLine(Base):
    """A cost-coded budget line (the control account of the system).

    Only `original_budget` is stored; approved changes, commitments, actuals
    and forecasts are derived by app.services.forecast_service so there is a
    single source of truth and no denormalized drift.
    """

    __tablename__ = "budget_lines"
    __table_args__ = (UniqueConstraint("project_id", "cost_code", name="uq_budget_project_costcode"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), nullable=False, index=True)
    cost_code: Mapped[str] = mapped_column(String(50), nullable=False)
    description: Mapped[str] = mapped_column(String(255), nullable=False)
    category: Mapped[CostCategory] = mapped_column(
        _enum(CostCategory), nullable=False, default=CostCategory.GENERAL_CONDITIONS
    )
    original_budget: Mapped[Decimal] = mapped_column(Numeric(16, 2), nullable=False, default=Decimal("0"))
    # PM-entered cost-to-complete; when set it overrides the computed ETC for
    # this line (EAC = actual + manual_etc). Null = use the selected method.
    manual_etc: Mapped[Decimal | None] = mapped_column(Numeric(16, 2))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False
    )

    project = relationship("Project", back_populates="budget_lines")
    cost_entries = relationship("CostEntry", back_populates="budget_line", cascade="all, delete-orphan")


class CostEntry(Base):
    """Dated actual-cost posting against a budget line (invoice, payroll, etc.)."""

    __tablename__ = "cost_entries"

    id: Mapped[int] = mapped_column(primary_key=True)
    budget_line_id: Mapped[int] = mapped_column(ForeignKey("budget_lines.id"), nullable=False, index=True)
    entry_date: Mapped[date] = mapped_column(Date, nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(16, 2), nullable=False)
    description: Mapped[str | None] = mapped_column(String(255))
    created_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False
    )

    budget_line = relationship("BudgetLine", back_populates="cost_entries")


class ForecastSnapshot(Base):
    """Point-in-time project forecast, for trend/burn-down reporting."""

    __tablename__ = "forecast_snapshots"

    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), nullable=False, index=True)
    as_of: Mapped[date] = mapped_column(Date, nullable=False)
    method: Mapped[ForecastMethod] = mapped_column(
        _enum(ForecastMethod), nullable=False, default=ForecastMethod.REMAINING_BUDGET
    )
    total_current_budget: Mapped[Decimal] = mapped_column(Numeric(16, 2), nullable=False)
    total_committed: Mapped[Decimal] = mapped_column(Numeric(16, 2), nullable=False)
    total_actual: Mapped[Decimal] = mapped_column(Numeric(16, 2), nullable=False)
    total_etc: Mapped[Decimal] = mapped_column(Numeric(16, 2), nullable=False)
    total_eac: Mapped[Decimal] = mapped_column(Numeric(16, 2), nullable=False)
    total_vac: Mapped[Decimal] = mapped_column(Numeric(16, 2), nullable=False)
    created_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False
    )
