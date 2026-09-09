from sqlalchemy import Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base_class import Base


class CostCode(Base):
    """CSI MasterFormat reference library (WBS backbone).

    Seeded from app/data/csi_masterformat_2022.csv (BMI cost-code workbook).
    Codes are canonical "XX YY ZZ". Hierarchy:
      level 1 = Division   (XX 00 00) — first two digits are the master number
      level 2 = Section    (XX YY 00)
      level 3 = Detail     (XX YY ZZ)
    Budget lines reference codes by their digits; custom (non-CSI) codes are
    allowed and still roll up to their division by the first two digits.
    """

    __tablename__ = "cost_codes"

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(20), unique=True, index=True, nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    division: Mapped[str] = mapped_column(String(2), index=True, nullable=False)
    level: Mapped[int] = mapped_column(Integer, nullable=False)
