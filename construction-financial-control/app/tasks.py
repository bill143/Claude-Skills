"""Optional Celery worker: nightly forecast snapshots per active project.

Run:  celery -A app.tasks worker --beat --loglevel=info
Requires Redis (see docker-compose 'worker' service). The API works fully
without this worker; snapshots can also be taken on demand via the API.
"""
from celery import Celery
from celery.schedules import crontab

from app.core.config import settings

celery_app = Celery("cfcs", broker=settings.REDIS_URL, backend=settings.REDIS_URL)

celery_app.conf.beat_schedule = {
    "nightly-forecast-snapshots": {
        "task": "app.tasks.snapshot_all_projects",
        "schedule": crontab(hour=2, minute=0),
    }
}


@celery_app.task
def snapshot_all_projects() -> int:
    from sqlalchemy import select

    from app.db.session import SessionLocal
    from app.models.project import Project
    from app.services import forecast_service

    db = SessionLocal()
    try:
        projects = db.execute(select(Project).where(Project.is_active.is_(True))).scalars().all()
        for project in projects:
            forecast_service.create_snapshot(db, project)
        db.commit()
        return len(projects)
    finally:
        db.close()
