"""Shared fixtures: a fresh SQLite-backed app + TestClient per test, so
tests never touch a real Postgres instance and can't leak state between
each other."""
import os
import uuid
from pathlib import Path

import pytest

os.environ.setdefault("SECRET_KEY", "test-only-secret-not-for-real-use")

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from fastapi.testclient import TestClient

from app.config import get_settings
from app.database import Base, get_db
from app.main import app


@pytest.fixture()
def db_session(tmp_path, monkeypatch):
    monkeypatch.setenv("UPLOAD_DIR", str(tmp_path / "uploads"))
    get_settings.cache_clear()
    db_path = tmp_path / f"test-{uuid.uuid4().hex}.db"
    engine = create_engine(f"sqlite:///{db_path}")
    Base.metadata.create_all(engine)
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()
        app.dependency_overrides.pop(get_db, None)
        Path(db_path).unlink(missing_ok=True)


@pytest.fixture()
def client(db_session):
    return TestClient(app)


@pytest.fixture()
def repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


@pytest.fixture()
def register_and_login(client):
    def _do(email="tester@example.com", password="correct-horse-battery"):
        client.post("/api/auth/register", json={"email": email, "password": password})
        resp = client.post("/api/auth/login", data={"username": email, "password": password})
        token = resp.json()["access_token"]
        return {"Authorization": f"Bearer {token}"}

    return _do
