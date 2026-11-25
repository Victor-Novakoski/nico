import re
import time

import pytest
from conftest import SESSION_TEST_SECRET, TEST_PASSWORD, TEST_USERNAME
from fastapi.testclient import TestClient

from nico import auth
from nico.app import app
from nico.routes import session

USER_ID = "00000000-0000-0000-0000-000000000001"


@pytest.fixture
def secret(monkeypatch):
    monkeypatch.setenv("NICO_SECRET_KEY", SESSION_TEST_SECRET)


def login(client, password=TEST_PASSWORD, username=TEST_USERNAME):
    return client.post("/api/login", json={"username": username, "password": password})


# Token (sem banco)


def test_token_roundtrip(secret):
    assert auth.verify_session(auth.sign_session(USER_ID)) == USER_ID


def test_token_tampered_is_invalid(secret):
    token = auth.sign_session(USER_ID)
    assert auth.verify_session(token[:-1] + ("0" if token[-1] != "0" else "1")) is None
    other = auth.sign_session("00000000-0000-0000-0000-000000000002")
    assert auth.verify_session(other.split(".")[0] + "." + token.split(".")[1]) is None


def test_token_expired_is_invalid(secret):
    token = auth.sign_session(USER_ID, now=time.time() - auth.SESSION_SECONDS - 10)
    assert auth.verify_session(token) is None


@pytest.mark.parametrize("token", ["", "x", "a.b", "a.b.c", "!!!.zzz", "é.é"])
def test_token_malformed_is_invalid(secret, token):
    assert auth.verify_session(token) is None


def test_token_needs_secret(monkeypatch):
    monkeypatch.delenv("NICO_SECRET_KEY", raising=False)
    with pytest.raises(RuntimeError):
        auth.sign_session(USER_ID)


# Rotas sem cookie (sem banco)


def test_every_api_route_except_open_ones_requires_login(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setenv("NICO_SECRET_KEY", SESSION_TEST_SECRET)
    open_paths = {"/api/health", "/api/login"}
    seen = 0
    with TestClient(app, base_url="https://testserver") as client:
        # O OpenAPI lista as rotas de routers incluídos (app.routes os esconde).
        for path, methods in app.openapi()["paths"].items():
            if not path.startswith("/api") or path in open_paths:
                continue
            url = re.sub(r"\{[^}]+\}", "x", path)
            for method in methods:
                response = client.request(method.upper(), url)
                assert response.status_code == 401, f"{method.upper()} {path} sem login"
                seen += 1
    assert seen >= 2


def test_forged_cookie_is_401_without_touching_database(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setenv("NICO_SECRET_KEY", SESSION_TEST_SECRET)
    with TestClient(app, base_url="https://testserver") as client:
        client.cookies.set("nico_session", "lixo.lixo")
        assert client.get("/api/me").status_code == 401


# Login (com banco)


def test_login_ok_sets_secure_cookie(client):
    response = login(client)
    assert response.status_code == 200
    assert response.json() == {"username": TEST_USERNAME}
    header = response.headers["set-cookie"].lower()
    assert "nico_session=" in header
    for part in ("httponly", "secure", "samesite=lax", "path=/", "max-age=2592000"):
        assert part in header
    me = client.get("/api/me")
    assert me.status_code == 200
    assert me.json()["username"] == TEST_USERNAME
    assert me.json()["person_id"]


def test_login_wrong_password_and_unknown_user_look_the_same(client):
    wrong = login(client, password="errada-123")
    unknown = login(client, username="ninguem")
    assert wrong.status_code == unknown.status_code == 401
    assert wrong.json() == unknown.json() == {"detail": "Usuário ou senha incorretos"}
    assert "set-cookie" not in wrong.headers


def test_tampered_cookie_is_401(logged_client):
    token = logged_client.cookies.get("nico_session")
    logged_client.cookies.set("nico_session", token[:-1] + ("0" if token[-1] != "0" else "1"))
    assert logged_client.get("/api/me").status_code == 401


def test_expired_cookie_is_401(client):
    login(client)
    user_id = auth.verify_session(client.cookies.get("nico_session"))
    old = auth.sign_session(user_id, now=time.time() - auth.SESSION_SECONDS - 5)
    client.cookies.set("nico_session", old)
    assert client.get("/api/me").status_code == 401


def test_cookie_for_deleted_user_is_401(logged_client, auth_env):
    import psycopg

    with psycopg.connect(auth_env) as conn:
        conn.execute("delete from app_user")
    assert logged_client.get("/api/me").status_code == 401


def test_logout_clears_cookie(logged_client):
    response = logged_client.post("/api/logout")
    assert response.status_code == 204
    assert logged_client.get("/api/me").status_code == 401


def test_logout_requires_login(client):
    assert client.post("/api/logout").status_code == 401


def test_rate_limit_blocks_after_five_failures(client, monkeypatch):
    clock = [1000.0]
    monkeypatch.setattr(session, "_now", lambda: clock[0])
    for _ in range(5):
        assert login(client, password="errada-123").status_code == 401
    blocked = login(client)  # até a senha certa fica bloqueada
    assert blocked.status_code == 429
    clock[0] += session.WINDOW_SECONDS + 1
    assert login(client).status_code == 200


def test_successful_login_resets_counter(client):
    for _ in range(4):
        assert login(client, password="errada-123").status_code == 401
    assert login(client).status_code == 200
    for _ in range(4):
        assert login(client, password="errada-123").status_code == 401
    assert login(client).status_code == 200


def test_signed_cookie_with_non_uuid_id_is_401(client):
    client.cookies.set(auth.SESSION_COOKIE, auth.sign_session("nao-e-uuid"))
    assert client.get("/api/me").status_code == 401
