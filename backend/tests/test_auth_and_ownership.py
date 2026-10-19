def test_register_then_login(client):
    r = client.post("/api/auth/register", json={"email": "a@example.com", "password": "correct-horse"})
    assert r.status_code == 201
    assert r.json()["email"] == "a@example.com"
    assert "hashed_password" not in r.json()

    r = client.post("/api/auth/login", data={"username": "a@example.com", "password": "correct-horse"})
    assert r.status_code == 200
    assert r.json()["token_type"] == "bearer"
    assert r.json()["access_token"]


def test_duplicate_email_rejected(client):
    client.post("/api/auth/register", json={"email": "a@example.com", "password": "correct-horse"})
    r = client.post("/api/auth/register", json={"email": "a@example.com", "password": "something-else"})
    assert r.status_code == 400


def test_login_wrong_password_rejected(client):
    client.post("/api/auth/register", json={"email": "a@example.com", "password": "correct-horse"})
    r = client.post("/api/auth/login", data={"username": "a@example.com", "password": "wrong"})
    assert r.status_code == 401


def test_endpoints_require_auth(client):
    assert client.get("/api/projects").status_code == 401
    assert client.post("/api/projects", json={"name": "x"}).status_code == 401
    assert client.get("/api/controls").status_code == 401


def test_me_returns_current_user(client, register_and_login):
    headers = register_and_login(email="alice@example.com")
    r = client.get("/api/auth/me", headers=headers)
    assert r.status_code == 200
    assert r.json()["email"] == "alice@example.com"


def test_project_isolation_between_users(client, register_and_login):
    alice = register_and_login(email="alice@example.com")
    bob = register_and_login(email="bob@example.com")

    r = client.post("/api/projects", json={"name": "Alice's App"}, headers=alice)
    assert r.status_code == 201
    project_id = r.json()["id"]

    # Alice sees it.
    assert len(client.get("/api/projects", headers=alice).json()) == 1
    # Bob's list is empty.
    assert len(client.get("/api/projects", headers=bob).json()) == 0
    # Bob can't fetch it by ID either — 404, not 403, so a valid ID can't
    # be used to tell "exists but not yours" apart from "doesn't exist".
    assert client.get(f"/api/projects/{project_id}", headers=bob).status_code == 404
    # Bob can't delete it.
    assert client.delete(f"/api/projects/{project_id}", headers=bob).status_code == 404
    # Alice can fetch and delete her own.
    assert client.get(f"/api/projects/{project_id}", headers=alice).status_code == 200


def test_apps_and_test_runs_scoped_to_owner(client, register_and_login):
    alice = register_and_login(email="alice@example.com")
    bob = register_and_login(email="bob@example.com")

    project_id = client.post("/api/projects", json={"name": "p"}, headers=alice).json()["id"]
    r = client.post(
        f"/api/projects/{project_id}/apps",
        files={"file": ("app.apk", b"fake-apk-bytes", "application/octet-stream")},
        headers=alice,
    )
    assert r.status_code == 201
    app_id = r.json()["id"]

    # Bob can't see or act on Alice's app.
    assert client.get(f"/api/apps/{app_id}", headers=bob).status_code == 404
    assert client.post(f"/api/apps/{app_id}/test-runs", json={}, headers=bob).status_code == 404

    # Alice can create a test run on her own app.
    r = client.post(f"/api/apps/{app_id}/test-runs", json={}, headers=alice)
    assert r.status_code == 201
    test_run_id = r.json()["id"]

    # Bob can't see the test run, its results, or its report.
    assert client.get(f"/api/test-runs/{test_run_id}", headers=bob).status_code == 404
    assert client.get(f"/api/test-runs/{test_run_id}/results", headers=bob).status_code == 404
    assert client.get(f"/api/test-runs/{test_run_id}/report.md", headers=bob).status_code == 404

    # Alice can.
    assert client.get(f"/api/test-runs/{test_run_id}", headers=alice).status_code == 200
