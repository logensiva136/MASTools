import uuid

from app import models
from app.services.automated_checks import (
    AUTOMATED_CONTROL_MAPPERS,
    apply_automated_results,
    _map_anti_dynamic_analysis,
    _map_ipc_exported_components,
    _map_network_cleartext,
    _map_permission_minimization,
)


def test_permission_minimization_passes_with_no_sensitive_permissions():
    status, _ = _map_permission_minimization({"sensitive_permissions": []})
    assert status == models.ResultStatus.passed


def test_permission_minimization_flags_for_manual_review_when_present():
    status, evidence = _map_permission_minimization(
        {"sensitive_permissions": ["android.permission.READ_SMS"]}
    )
    assert status == models.ResultStatus.manual_review
    assert "READ_SMS" in evidence


def test_ipc_exported_components_passes_when_none_exported():
    status, _ = _map_ipc_exported_components({})
    assert status == models.ResultStatus.passed


def test_ipc_exported_components_flags_when_present():
    status, evidence = _map_ipc_exported_components({"exported_activities": [".MainActivity"]})
    assert status == models.ResultStatus.manual_review
    assert "MainActivity" in evidence


def test_anti_dynamic_analysis_fails_when_debuggable():
    status, _ = _map_anti_dynamic_analysis({"debuggable": True})
    assert status == models.ResultStatus.failed


def test_anti_dynamic_analysis_passes_when_not_debuggable():
    status, _ = _map_anti_dynamic_analysis({"debuggable": False})
    assert status == models.ResultStatus.passed


def test_anti_dynamic_analysis_none_when_unknown():
    assert _map_anti_dynamic_analysis({}) is None


def test_network_cleartext_fails_when_allowed():
    status, _ = _map_network_cleartext({"uses_cleartext_traffic": True})
    assert status == models.ResultStatus.failed


def test_network_cleartext_passes_when_disabled():
    status, _ = _map_network_cleartext({"uses_cleartext_traffic": False})
    assert status == models.ResultStatus.passed


def _make_control(db, code, category="TEST"):
    control = models.MasvsControl(
        version="MASVS-v2.1",
        code=code,
        category=category,
        title=code,
        description=code,
        applies_to=["android", "ios"],
        automatable=code in AUTOMATED_CONTROL_MAPPERS,
    )
    db.add(control)
    db.flush()
    return control


def test_apply_automated_results_updates_only_mapped_controls(db_session):
    db = db_session
    project = models.Project(id=uuid.uuid4(), owner_id=uuid.uuid4(), name="p")
    # owner_id has an FK, but sqlite in tests doesn't enforce it by default —
    # this test only cares about the control-mapping logic, not ownership.
    db.add(project)
    app_row = models.App(
        id=uuid.uuid4(),
        project_id=project.id,
        filename="app.apk",
        file_path="/tmp/app.apk",
        platform=models.Platform.android,
        extracted_metadata={
            "sensitive_permissions": ["android.permission.CAMERA"],
            "debuggable": True,
            "uses_cleartext_traffic": False,
            "exported_activities": [],
            "exported_services": [],
            "exported_receivers": [],
            "exported_providers": [],
        },
    )
    db.add(app_row)
    test_run = models.TestRun(id=uuid.uuid4(), app_id=app_row.id, catalog_version="MASVS-v2.1")
    db.add(test_run)

    automated_control = _make_control(db, "MASVS-PRIVACY-1")
    manual_control = _make_control(db, "MASVS-AUTH-1")

    for control in (automated_control, manual_control):
        db.add(
            models.ControlResult(
                test_run_id=test_run.id,
                control_id=control.id,
                status=models.ResultStatus.pending,
                method=models.ResultMethod.manual,
            )
        )
    db.flush()

    apply_automated_results(db, app_row, test_run)
    db.flush()

    results = {r.control.code: r for r in db.query(models.ControlResult).join(models.MasvsControl).all()}
    assert results["MASVS-PRIVACY-1"].method == models.ResultMethod.automated
    assert results["MASVS-PRIVACY-1"].status == models.ResultStatus.manual_review  # camera is sensitive
    # Not one of the four automated controls — must be left untouched.
    assert results["MASVS-AUTH-1"].method == models.ResultMethod.manual
    assert results["MASVS-AUTH-1"].status == models.ResultStatus.pending


def test_apply_automated_results_noop_without_metadata(db_session):
    db = db_session
    project = models.Project(id=uuid.uuid4(), owner_id=uuid.uuid4(), name="p")
    db.add(project)
    app_row = models.App(
        id=uuid.uuid4(),
        project_id=project.id,
        filename="app.apk",
        file_path="/tmp/app.apk",
        platform=models.Platform.android,
        extracted_metadata=None,
    )
    db.add(app_row)
    test_run = models.TestRun(id=uuid.uuid4(), app_id=app_row.id, catalog_version="MASVS-v2.1")
    db.add(test_run)
    control = _make_control(db, "MASVS-PRIVACY-1")
    result = models.ControlResult(
        test_run_id=test_run.id,
        control_id=control.id,
        status=models.ResultStatus.pending,
        method=models.ResultMethod.manual,
    )
    db.add(result)
    db.flush()

    apply_automated_results(db, app_row, test_run)
    db.flush()

    db.refresh(result)
    assert result.status == models.ResultStatus.pending
    assert result.method == models.ResultMethod.manual
