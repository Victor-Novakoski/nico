import pytest
from fastapi.testclient import TestClient

from nico import config
from nico.app import app

client = TestClient(app)


def test_health_returns_ok():
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json() == {"ok": True}


def test_require_reads_environment(monkeypatch):
    monkeypatch.setenv("NICO_TEST_SECRET", "x")
    assert config.require("NICO_TEST_SECRET") == "x"


def test_require_fails_without_default(monkeypatch):
    monkeypatch.delenv("NICO_TEST_SECRET", raising=False)
    with pytest.raises(RuntimeError):
        config.require("NICO_TEST_SECRET")
