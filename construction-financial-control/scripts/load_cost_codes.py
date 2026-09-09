"""Load the CSI MasterFormat cost-code library into the database.

Run after `alembic upgrade head` in stage/prod (dev/demo seeding happens via
scripts/seed.py or the dev startup path). Idempotent: skips if already loaded.

Usage:  python scripts/load_cost_codes.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.db.session import SessionLocal  # noqa: E402
from app.services.wbs_service import seed_cost_codes  # noqa: E402


def main() -> None:
    with SessionLocal() as db:
        loaded = seed_cost_codes(db)
    if loaded:
        print(f"Loaded {loaded} CSI MasterFormat cost codes.")
    else:
        print("Cost-code library already loaded; nothing to do.")


if __name__ == "__main__":
    main()
