import pytest
from fastapi.testclient import TestClient

from nico.app import app


@pytest.fixture
def client(db_url, monkeypatch):
    monkeypatch.setenv("DATABASE_URL", db_url)
    with TestClient(app) as client:
        yield client


def test_empty_list(client):
    response = client.get("/api/people")
    assert response.status_code == 200
    assert response.json() == []


def test_create_and_list(client):
    response = client.post("/api/people", json={"name": "Fulana"})
    assert response.status_code == 201
    created = response.json()
    assert created["name"] == "Fulana"
    assert created["id"]
    assert client.get("/api/people").json() == [created]


def test_list_is_sorted_by_name_ignoring_case(client):
    for name in ["beltrano", "Fulana", "Ciclano"]:
        client.post("/api/people", json={"name": name})
    names = [p["name"] for p in client.get("/api/people").json()]
    assert names == ["beltrano", "Ciclano", "Fulana"]


@pytest.mark.parametrize("name", ["", "   ", "x" * 81])
def test_invalid_name_is_422(client, name):
    assert client.post("/api/people", json={"name": name}).status_code == 422
    assert client.get("/api/people").json() == []


def test_name_is_trimmed(client):
    response = client.post("/api/people", json={"name": "  Beltrano  "})
    assert response.status_code == 201
    assert response.json()["name"] == "Beltrano"


def test_max_length_name_is_accepted(client):
    assert client.post("/api/people", json={"name": "x" * 80}).status_code == 201
