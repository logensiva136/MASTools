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


# --- Mapping from extracted metadata -> automated ControlResult updates ---
# Each mapper receives the extracted_metadata dict and returns
# (status, evidence) or None if it has nothing to say for that control.
#
# Control codes below are real MASVS v2.1 codes (see data/catalog/README.md
# for how the catalog is generated) and were chosen by tracing each check
# through its MASWE weakness to that weakness's own masvs-v2 mapping:
#
#   sensitive permissions  -> MASWE-0066 "Inadequate Permission Management"
#                              -> MASVS-PRIVACY-1 "minimizes access to
#                                 sensitive data and resources"
#   exported components     -> MASWE-0032 "Insecure Intents"
#                              -> MASVS-PLATFORM-1 "uses IPC mechanisms securely"
#   debuggable flag          -> MASWE-0063 "Debug Mechanisms Not Disabled"
#                              -> MASVS-RESILIENCE-4 "implements anti-dynamic
#                                 analysis techniques"
#   cleartext traffic        -> MASWE-0026/0027 (network cleartext weaknesses)
#                              -> MASVS-NETWORK-1 "secures all network traffic"
#
# Keep this in sync with data/catalog/generate_catalog.py's
# AUTOMATED_CONTROLS set, which marks exactly these four controls
# `automatable: true` in the generated catalog.

def _map_permission_minimization(meta: dict) -> tuple[models.ResultStatus, str] | None:
    sensitive = meta.get("sensitive_permissions") or []
    if not sensitive:
        return models.ResultStatus.passed, "No permissions in the sensitive-by-default set were declared."
    return (
        models.ResultStatus.manual_review,
        f"Declared sensitive permissions, justification not yet reviewed: {', '.join(sensitive)}",
    )


def _map_ipc_exported_components(meta: dict) -> tuple[models.ResultStatus, str] | None:
    exported = {
        "activities": meta.get("exported_activities") or [],
        "services": meta.get("exported_services") or [],
        "receivers": meta.get("exported_receivers") or [],
        "providers": meta.get("exported_providers") or [],
    }
    total = sum(len(v) for v in exported.values())
    if total == 0:
        return models.ResultStatus.passed, "No exported components found."
    detail = "; ".join(f"{k}: {', '.join(v)}" for k, v in exported.items() if v)
    return models.ResultStatus.manual_review, f"Exported components require manual review of access control: {detail}"


def _map_anti_dynamic_analysis(meta: dict) -> tuple[models.ResultStatus, str] | None:
    if meta.get("debuggable") is None:
        return None
    if meta["debuggable"]:
        return models.ResultStatus.failed, "AndroidManifest declares android:debuggable=\"true\"."
    return models.ResultStatus.passed, "android:debuggable is not set to true."


def _map_network_cleartext(meta: dict) -> tuple[models.ResultStatus, str] | None:
    if meta.get("uses_cleartext_traffic") is None:
        return None
    if meta["uses_cleartext_traffic"]:
        return (
            models.ResultStatus.failed,
            "App does not explicitly disable cleartext traffic (usesCleartextTraffic != \"false\").",
        )
    return models.ResultStatus.passed, "usesCleartextTraffic is explicitly set to false."


AUTOMATED_CONTROL_MAPPERS = {
    "MASVS-PRIVACY-1": _map_permission_minimization,
    "MASVS-PLATFORM-1": _map_ipc_exported_components,
    "MASVS-RESILIENCE-4": _map_anti_dynamic_analysis,
    "MASVS-NETWORK-1": _map_network_cleartext,
}


def apply_automated_results(db, app_row, test_run) -> None:
    """Writes automated ControlResult updates for one test run, based on
    app_row.extracted_metadata. Safe to call multiple times (idempotent)."""
    if not app_row.extracted_metadata:
        return

    results = (
        db.query(models.ControlResult)
        .join(models.MasvsControl)
        .filter(models.ControlResult.test_run_id == test_run.id)
        .all()
    )
    by_code = {r.control.code: r for r in results}

    for code, mapper in AUTOMATED_CONTROL_MAPPERS.items():
        result = by_code.get(code)
        if not result:
            continue
        outcome = mapper(app_row.extracted_metadata)
        if outcome is None:
            continue
        status, evidence = outcome
        result.status = status
        result.method = models.ResultMethod.automated
        result.evidence = evidence

    db.commit()


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

            return {"ok": True, "metadata": metadata}
        except Exception as exc:  # noqa: BLE001
            logger.exception("Static analysis failed for app %s", app_id)
            app_row.status = models.AppStatus.failed
            db.commit()
            return {"ok": False, "error": str(exc)}
    finally:
        db.close()
