"""Work Breakdown Structure: CSI MasterFormat library + hierarchical rollups.

Hierarchy (per the BMI cost-code workbook):
  Level 1  Division  = first two digits of the code (the master number)
  Level 2  Section   = XX YY 00
  Level 3  Detail    = XX YY ZZ (budget lines usually live here)

`project_wbs` returns the full tree with financial rollups at every level so
the UI renders Division -> Section -> Line with subtotals for budget,
committed, actual, ETC, EAC, and VAC.
"""
import csv
from pathlib import Path

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.cost_code import CostCode
from app.models.enums import ForecastMethod
from app.models.project import Project
from app.services import forecast_service
from app.services.forecast_service import code_digits, division_of, normalize_code  # noqa: F401

CSI_CSV_PATH = Path(__file__).resolve().parent.parent / "data" / "csi_masterformat_2022.csv"

ROLLUP_KEYS = ("original_budget", "approved_changes", "current_budget", "committed",
               "actual", "etc", "eac", "vac")


def seed_cost_codes(db: Session) -> int:
    """Load the bundled CSI MasterFormat library if the table is empty. Idempotent."""
    existing = db.execute(select(func.count(CostCode.id))).scalar_one()
    if existing:
        return 0
    with open(CSI_CSV_PATH, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    db.add_all(
        CostCode(code=row["code"], title=row["title"], division=row["division"],
                 level=int(row["level"]))
        for row in rows
    )
    db.commit()
    return len(rows)


def lookup_title(db: Session, raw_code: str) -> str | None:
    """Title for a code from the reference library (exact 6-digit match)."""
    digits = code_digits(raw_code)
    if len(digits) != 6:
        return None
    row = db.execute(
        select(CostCode.title).where(CostCode.code == normalize_code(raw_code))
    ).scalar_one_or_none()
    return row


def _reference_titles(db: Session, divisions: set[str]) -> dict[str, str]:
    """{code -> title} for all reference rows in the given divisions."""
    if not divisions:
        return {}
    rows = db.execute(select(CostCode.code, CostCode.title)
                      .where(CostCode.division.in_(divisions))).all()
    return {code: title for code, title in rows}


def _zero_rollup() -> dict:
    return {key: 0.0 for key in ROLLUP_KEYS}


def _accumulate(rollup: dict, metrics: dict) -> None:
    for key in ROLLUP_KEYS:
        rollup[key] = round(rollup[key] + metrics[key], 2)


def project_wbs(
    db: Session,
    project: Project,
    method: ForecastMethod = ForecastMethod.REMAINING_BUDGET,
    percent_complete: float | None = None,
) -> dict:
    """Division -> Section -> Line tree with financial rollups at every level."""
    lines = [
        forecast_service.line_metrics(db, bl, method=method, percent_complete=percent_complete)
        for bl in project.budget_lines
    ]
    titles = _reference_titles(db, {row["division"] for row in lines})

    divisions: dict[str, dict] = {}
    totals = _zero_rollup()
    for row in lines:
        digits = code_digits(row["cost_code"])
        div_key = row["division"]
        section_digits = digits[:4] if len(digits) >= 4 else div_key + "00"
        section_code = f"{section_digits[0:2]} {section_digits[2:4]} 00"

        division = divisions.setdefault(div_key, {
            "division": div_key,
            "title": titles.get(f"{div_key} 00 00", f"Division {div_key}"),
            "rollup": _zero_rollup(),
            "sections": {},
        })
        section = division["sections"].setdefault(section_code, {
            "code": section_code,
            "title": titles.get(section_code, "General"),
            "rollup": _zero_rollup(),
            "lines": [],
        })
        row = {**row, "cost_code": normalize_code(row["cost_code"])}
        section["lines"].append(row)
        _accumulate(section["rollup"], row)
        _accumulate(division["rollup"], row)
        _accumulate(totals, row)

    tree = []
    for div_key in sorted(divisions):
        division = divisions[div_key]
        division["sections"] = [
            {**section, "lines": sorted(section["lines"], key=lambda r: r["cost_code"])}
            for _, section in sorted(division["sections"].items())
        ]
        tree.append(division)

    return {
        "project_id": project.id,
        "method": method.value,
        "divisions": tree,
        "totals": totals,
    }
