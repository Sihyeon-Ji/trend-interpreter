from uuid import uuid4

import pytest
from builder_cup import database
from builder_cup.config import Settings
from builder_cup.main import create_app
from fastapi.testclient import TestClient


def test_lab_is_disabled_by_default():
    with TestClient(create_app(Settings(_env_file=None))) as client:
        assert client.post("/api/lab/records").status_code == 404
        assert client.get(f"/api/lab/records/{uuid4()}").status_code == 404


def test_lab_rejects_cloud_run(monkeypatch):
    monkeypatch.setenv("K_SERVICE", "builder-cup")
    with pytest.raises(RuntimeError, match="Database lab is only available in local mock mode"):
        create_app(Settings(_env_file=None, database_lab_enabled=True, demo_api_key="test-only"))


def test_database_failure_is_reported_without_secrets(monkeypatch):
    def unavailable(_settings):
        raise database.DatabaseUnavailable("credential-must-not-appear")

    monkeypatch.setattr(database, "create_record", unavailable)
    with TestClient(create_app(Settings(_env_file=None, database_lab_enabled=True))) as client:
        response = client.post("/api/lab/records")
        assert response.status_code == 503
        assert response.json()["error"]["code"] == "database_unavailable"
        assert response.json()["error"]["request_id"] == response.headers["X-Request-ID"]
        assert "credential-must-not-appear" not in response.text


def test_missing_secret_file_has_a_safe_database_error(tmp_path):
    settings = Settings(_env_file=None, database_password_file=str(tmp_path / "absent"))
    with pytest.raises(database.DatabaseUnavailable, match="^database_unavailable$"):
        database.create_record(settings)
