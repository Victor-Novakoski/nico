import uuid

import psycopg
from fastapi.testclient import TestClient

from nico.auth import hash_password

URL = "/api/me/settings"


def make_method(client, name="Pix da casa") -> str:
    person_id = client.get("/api/me").json()["person_id"]
    response = client.post(
        "/api/payment-methods", json={"name": name, "owner_id": person_id, "kind": "pix"}
    )
    assert response.status_code == 201
    return response.json()["id"]


def test_requires_login(client):
    assert client.get(URL).status_code == 401
    assert client.patch(URL, json={"default_method_id": None}).status_code == 401


def test_default_settings(logged_client):
    assert logged_client.get(URL).json() == {"default_method_id": None, "ai_enabled": False}


def test_set_change_and_clear(logged_client):
    first = make_method(logged_client, "Pix da casa")
    second = make_method(logged_client, "Carteira")

    response = logged_client.patch(URL, json={"default_method_id": first})
    assert response.status_code == 200
    assert response.json() == {"default_method_id": first, "ai_enabled": False}
    assert logged_client.get(URL).json()["default_method_id"] == first

    assert (
        logged_client.patch(URL, json={"default_method_id": second}).json()["default_method_id"]
        == second
    )

    response = logged_client.patch(URL, json={"default_method_id": None})
    assert response.status_code == 200
    assert response.json()["default_method_id"] is None
    assert logged_client.get(URL).json()["default_method_id"] is None


def test_unknown_method_is_422(logged_client):
    response = logged_client.patch(URL, json={"default_method_id": str(uuid.uuid4())})
    assert response.status_code == 422
    assert response.json()["detail"] == "Meio de pagamento não encontrado"
    assert logged_client.get(URL).json()["default_method_id"] is None


def test_empty_body_is_422(logged_client):
    method = make_method(logged_client)
    logged_client.patch(URL, json={"default_method_id": method})
    assert logged_client.patch(URL, json={}).status_code == 422
    assert logged_client.get(URL).json()["default_method_id"] == method


def test_setting_belongs_to_logged_user_only(logged_client, auth_env):
    method = make_method(logged_client)
    with psycopg.connect(auth_env) as conn:
        person_id = conn.execute(
            "insert into person (name) values ('Beltrana') returning id"
        ).fetchone()[0]
        conn.execute(
            "insert into app_user (person_id, username, password_hash) values (%s, %s, %s)",
            (person_id, "beltrana", hash_password("senha-inventada-2")),
        )
    assert logged_client.patch(URL, json={"default_method_id": method}).status_code == 200

    from nico.app import app

    # Sem `with`: não roda o lifespan de novo, o pool aberto pelo `client` é reaproveitado.
    other = TestClient(app, base_url="https://testserver")
    login = other.post("/api/login", json={"username": "beltrana", "password": "senha-inventada-2"})
    assert login.status_code == 200
    assert other.get(URL).json()["default_method_id"] is None
    assert other.patch(URL, json={"default_method_id": method}).status_code == 200
    assert other.patch(URL, json={"default_method_id": None}).status_code == 200

    # Limpar o principal da outra pessoa não mexe no da Fulana.
    assert logged_client.get(URL).json()["default_method_id"] == method


def test_ai_enabled_default_off_then_on_and_off(logged_client):
    assert logged_client.get(URL).json()["ai_enabled"] is False
    response = logged_client.patch(URL, json={"ai_enabled": True})
    assert response.status_code == 200
    assert response.json() == {"default_method_id": None, "ai_enabled": True}
    assert logged_client.get(URL).json()["ai_enabled"] is True
    response = logged_client.patch(URL, json={"ai_enabled": False})
    assert response.json()["ai_enabled"] is False
    assert logged_client.get(URL).json()["ai_enabled"] is False


def test_fields_do_not_touch_each_other(logged_client):
    method = make_method(logged_client)
    logged_client.patch(URL, json={"default_method_id": method})
    assert logged_client.patch(URL, json={"ai_enabled": True}).json() == {
        "default_method_id": method,
        "ai_enabled": True,
    }
    assert logged_client.patch(URL, json={"default_method_id": None}).json() == {
        "default_method_id": None,
        "ai_enabled": True,
    }
    assert logged_client.patch(
        URL, json={"default_method_id": method, "ai_enabled": False}
    ).json() == {
        "default_method_id": method,
        "ai_enabled": False,
    }


def test_ai_enabled_must_be_a_real_bool(logged_client):
    for value in ("true", 1, None):
        assert logged_client.patch(URL, json={"ai_enabled": value}).status_code == 422
    assert logged_client.get(URL).json()["ai_enabled"] is False


def test_unknown_field_is_422(logged_client):
    assert logged_client.patch(URL, json={"ai_enabled": True, "foo": 1}).status_code == 422
    assert logged_client.get(URL).json()["ai_enabled"] is False


def test_ai_enabled_belongs_to_logged_user_only(logged_client, auth_env):
    with psycopg.connect(auth_env) as conn:
        person_id = conn.execute(
            "insert into person (name) values ('Beltrana') returning id"
        ).fetchone()[0]
        conn.execute(
            "insert into app_user (person_id, username, password_hash) values (%s, %s, %s)",
            (person_id, "beltrana", hash_password("senha-inventada-2")),
        )
    assert logged_client.patch(URL, json={"ai_enabled": True}).status_code == 200

    from nico.app import app

    other = TestClient(app, base_url="https://testserver")
    login = other.post("/api/login", json={"username": "beltrana", "password": "senha-inventada-2"})
    assert login.status_code == 200
    assert other.get(URL).json()["ai_enabled"] is False
    assert other.patch(URL, json={"ai_enabled": True}).status_code == 200
    assert other.patch(URL, json={"ai_enabled": False}).status_code == 200
    assert logged_client.get(URL).json()["ai_enabled"] is True


def test_ai_enabled_requires_login(client):
    assert client.patch(URL, json={"ai_enabled": True}).status_code == 401
