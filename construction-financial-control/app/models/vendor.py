from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, Enum, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base_class import Base
from app.models.enums import VendorType


def _enum(e, length=32):
    return Enum(e, native_enum=False, length=length, values_callable=lambda x: [m.value for m in x])


class Vendor(Base):
    __tablename__ = "vendors"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    vendor_type: Mapped[VendorType] = mapped_column(
        _enum(VendorType), nullable=False, default=VendorType.SUBCONTRACTOR
    )
    trade: Mapped[str | None] = mapped_column(String(120))
    contact_name: Mapped[str | None] = mapped_column(String(255))
    contact_email: Mapped[str | None] = mapped_column(String(255))
    phone: Mapped[str | None] = mapped_column(String(50))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )
