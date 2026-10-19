"""Celery entry point for the worker container.

Runs as `celery -A tasks worker`. Imports the backend's SQLAlchemy models
directly (mounted read-only at /app, see docker-compose.yml) rather than
duplicating the schema here, so there is exactly one source of truth for
the data model.
"""
from __future__ import annotations

import logging

from celery import Celery

from app.config import get_settings
from app.database import SessionLocal
from app import models
from app.services.automated_checks import apply_automated_results

from checks import manifest_check

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("worker.tasks")

settings = get_settings()

celery_app = Celery(
    "mastools",
    broker=settings.broker_url,
    backend=settings.result_backend,
)
celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    task_track_started=True,
)


@celery_app.task(name="tasks.run_static_analysis")
def run_static_analysis(app_id: str) -> dict:
    db = SessionLocal()
    try:
        app_row = db.get(models.App, app_id)
        if not app_row:
            logger.error("App %s not found", app_id)
            return {"ok": False, "error": "app not found"}

        try:
            if app_row.platform == models.Platform.android:
                metadata = manifest_check.analyze_apk(app_row.file_path)
            else:
                logger.warning("iOS static analysis not yet implemented for app %s", app_id)
                metadata = {}

            app_row.extracted_metadata = metadata
            app_row.package_name = metadata.get("package_name") or app_row.package_name
            app_row.version_name = metadata.get("version_name") or app_row.version_name
            app_row.status = models.AppStatus.analyzed
            db.commit()

            for test_run in db.query(models.TestRun).filter(models.TestRun.app_id == app_row.id).all():
                apply_automated_results(db, app_row, test_run)
            db.commit()

            return {"ok": True, "metadata": metadata}
        except Exception as exc:  # noqa: BLE001
            logger.exception("Static analysis failed for app %s", app_id)
            app_row.status = models.AppStatus.failed
            db.commit()
            return {"ok": False, "error": str(exc)}
    finally:
        db.close()
