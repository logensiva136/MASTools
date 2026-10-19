"""Maps `App.extracted_metadata` (written by the worker's static checks) onto
automated `ControlResult` rows for a given test run.

Lives in the backend package — not the worker — so both sides can share one
copy: the worker image mounts `./backend:/app:ro` and has `/app` on its
PYTHONPATH specifically so it can import backend code like this instead of
duplicating it (see worker/Dockerfile). That also lets the API backfill a
test run created *after* a scan already ran, synchronously, with no Celery
round trip — see routers/test_runs.py's create_test_run.

Control codes below are real MASVS v2.1 codes (see data/catalog/README.md
for how the catalog is generated) and were chosen by tracing each check
through its MASWE weakness to that weakness's own masvs-v2 mapping:

  sensitive permissions  -> MASWE-0066 "Inadequate Permission Management"
                             -> MASVS-PRIVACY-1 "minimizes access to
                                sensitive data and resources"
  exported components     -> MASWE-0032 "Insecure Intents"
                             -> MASVS-PLATFORM-1 "uses IPC mechanisms securely"
  debuggable flag          -> MASWE-0063 "Debug Mechanisms Not Disabled"
                             -> MASVS-RESILIENCE-4 "implements anti-dynamic
                                analysis techniques"
  cleartext traffic        -> MASVS-NETWORK-1 "secures all network traffic"

Keep this in sync with data/catalog/generate_catalog.py's
AUTOMATED_CONTROLS set, which marks exactly these four controls
`automatable: true` in the generated catalog.
"""
from __future__ import annotations

from app import models


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
    app_row.extracted_metadata. Safe to call multiple times (idempotent).
    Does not commit — the caller controls the transaction."""
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
