import os

import psycopg
import pytest

from nico.auth import hash_password
from nico.migrate import migrate


@pytest.fixture
def db_url() -> str:
    """Banco de teste migrado e limpo (schema recriado); pula sem NICO_TEST_DATABASE_URL."""
    url = os.environ.get("NICO_TEST_DATABASE_URL")
    if not url:
        pytest.skip("NICO_TEST_DATABASE_URL não definida")
    with psycopg.connect(url, autocommit=True) as setup:
        setup.execute("drop schema public cascade")
        setup.execute("create schema public")
    migrate(url)
    return url


SESSION_TEST_SECRET = "chave-de-teste-inventada"
TEST_USERNAME = "fulana"
TEST_PASSWORD = "senha-inventada-1"


@pytest.fixture(autouse=True)
def _reset_login_limiter():
    from nico.routes import session

    session.reset_limiter()
    yield
    session.reset_limiter()


@pytest.fixture
def auth_env(db_url, monkeypatch) -> str:
    """Define DATABASE_URL e NICO_SECRET_KEY de teste e cria a usuária Fulana."""
    monkeypatch.setenv("DATABASE_URL", db_url)
    monkeypatch.setenv("NICO_SECRET_KEY", SESSION_TEST_SECRET)
    with psycopg.connect(db_url) as conn:
        person_id = conn.execute(
            "insert into person (name) values ('Fulana') returning id"
        ).fetchone()[0]
        conn.execute(
            "insert into app_user (person_id, username, password_hash) values (%s, %s, %s)",
            (person_id, TEST_USERNAME, hash_password(TEST_PASSWORD)),
        )
    return db_url


@pytest.fixture
def client(auth_env):
    """Cliente HTTPS (o cookie é Secure) sem login, com o app e o pool ligados."""
    from fastapi.testclient import TestClient

    from nico.app import app

    with TestClient(app, base_url="https://testserver") as c:
        yield c


@pytest.fixture
def logged_client(client):
    """Cliente já logado como Fulana; para testar rotas protegidas."""
    response = client.post(
        "/api/login", json={"username": TEST_USERNAME, "password": TEST_PASSWORD}
    )
    assert response.status_code == 200
    return client
