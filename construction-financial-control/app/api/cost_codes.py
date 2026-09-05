from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.cost_code import CostCode
from app.models.user import User

router = APIRouter(prefix="/cost-codes", tags=["cost-codes"])


@router.get("")
def search_cost_codes(
    q: str | None = Query(default=None, description="Search code or title"),
    division: str | None = Query(default=None, min_length=2, max_length=2),
    level: int | None = Query(default=None, ge=1, le=3),
    limit: int = Query(default=50, le=500),
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    query = select(CostCode)
    if division:
        query = query.where(CostCode.division == division)
    if level:
        query = query.where(CostCode.level == level)
    if q:
        text = f"%{q.strip()}%"
        query = query.where(CostCode.code.ilike(text) | CostCode.title.ilike(text))
    rows = db.execute(query.order_by(CostCode.code).limit(limit)).scalars().all()
    return [{"code": r.code, "title": r.title, "division": r.division, "level": r.level}
            for r in rows]


@router.get("/divisions")
def list_divisions(db: Session = Depends(get_db), _user: User = Depends(get_current_user)):
    rows = db.execute(
        select(CostCode.division, CostCode.title, func.count().label("codes"))
        .where(CostCode.level == 1)
        .group_by(CostCode.division, CostCode.title)
        .order_by(CostCode.division)
    ).all()
    counts: dict[str, int] = {
        division: count for division, count in
        db.execute(select(CostCode.division, func.count()).group_by(CostCode.division))
    }
    return [{"division": division, "title": title, "code_count": counts.get(division, 0)}
            for division, title, _ in rows]
