import uuid

from app import models


def _setup_project_and_app(client, headers, filename="app.apk"):
    project_id = client.post("/api/projects", json={"name": "p"}, headers=headers).json()["id"]
    app_id = client.post(
        f"/api/projects/{project_id}/apps",
        files={"file": (filename, b"fake-apk-bytes", "application/octet-stream")},
        headers=headers,
    ).json()["id"]
    return project_id, app_id


def test_create_test_run_creates_one_result_per_applicable_control(client, db_session, register_and_login):
    headers = register_and_login()
    _, app_id = _setup_project_and_app(client, headers)

    # Seed a couple of controls directly, like the catalog loader would.
    for code, applies_to in [("MASVS-STORAGE-1", ["android", "ios"]), ("MASVS-PLATFORM-1", ["android"])]:
        db_session.add(
            models.MasvsControl(
                version="MASVS-v2.1",
                code=code,
                category="TEST",
                title=code,
                description=code,
                applies_to=applies_to,
                automatable=False,
            )
        )
    db_session.commit()

    r = client.post(f"/api/apps/{app_id}/test-runs", json={}, headers=headers)
    assert r.status_code == 201
    test_run_id = r.json()["id"]

    results = client.get(f"/api/test-runs/{test_run_id}/results", headers=headers).json()
    assert len(results) == 2  # app is android, both controls apply to android


def test_create_test_run_backfills_existing_scan_results(client, db_session, register_and_login):
    """Regression test for the bug this fixed: a test run created *after* a
    scan already populated App.extracted_metadata must come back with the
    automated fields already filled in, with no need to re-trigger a scan."""
    headers = register_and_login()
    _, app_id = _setup_project_and_app(client, headers)

    db_session.add(
        models.MasvsControl(
            version="MASVS-v2.1",
            code="MASVS-NETWORK-1",
            category="NETWORK",
            title="t",
            description="d",
            applies_to=["android", "ios"],
            automatable=True,
        )
    )
    db_session.commit()

    # Simulate a scan having already run, the way worker/tasks.py would
    # after run_static_analysis finishes — set directly rather than via
    # the Celery task, since tests don't run a worker.
    app_row = db_session.query(models.App).filter(models.App.id == uuid.UUID(app_id)).one()
    app_row.extracted_metadata = {"uses_cleartext_traffic": False}
    db_session.commit()

    r = client.post(f"/api/apps/{app_id}/test-runs", json={}, headers=headers)
    assert r.status_code == 201
    test_run_id = r.json()["id"]

    results = client.get(f"/api/test-runs/{test_run_id}/results", headers=headers).json()
    network_result = next(r for r in results if r["control"]["code"] == "MASVS-NETWORK-1")
    assert network_result["method"] == "automated"
    assert network_result["status"] == "passed"
