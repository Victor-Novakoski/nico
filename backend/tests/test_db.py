from typing import Annotated

import psycopg
import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from nico.db import get_conn, lifespan

Conn = Annotated[psycopg.Connection, Depends(get_conn)]


def _app() -> FastAPI:
    app = FastAPI(lifespan=lifespan)

    @app.get("/one")
    def one(conn: Conn) -> dict[str, int]:
        return {"value": conn.execute("select 1").fetchone()[0]}

    @app.post("/person/{name}")
    def add(name: str, conn: Conn, fail: bool = False) -> dict[str, bool]:
        conn.execute("insert into person (name) values (%s)", (name,))
        if fail:
            raise RuntimeError("falhou")
        return {"ok": True}

    return app


def test_get_conn_runs_select_1(db_url, monkeypatch):
    monkeypatch.setenv("DATABASE_URL", db_url)
    with TestClient(_app()) as client:
        assert client.get("/one").json() == {"value": 1}


def test_transaction_commits_and_rolls_back(db_url, monkeypatch):
    monkeypatch.setenv("DATABASE_URL", db_url)
    with TestClient(_app(), raise_server_exceptions=False) as client:
        assert client.post("/person/Ana").status_code == 200
        assert client.post("/person/Bia?fail=true").status_code == 500
    with psycopg.connect(db_url) as check:
        assert check.execute("select name from person").fetchall() == [("Ana",)]


def test_without_database_url_app_starts_and_conn_is_503(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    with TestClient(_app()) as client:
        assert client.get("/one").status_code == 503


def test_real_app_health_without_database(monkeypatch):
    from nico.app import app

    monkeypatch.delenv("DATABASE_URL", raising=False)
    with TestClient(app) as client:
        assert client.get("/api/health").json() == {"ok": True}


@pytest.mark.parametrize("value", ["", None])
def test_create_pool_requires_url(monkeypatch, value):
    from nico.db import create_pool

    if value is None:
        monkeypatch.delenv("DATABASE_URL", raising=False)
    else:
        monkeypatch.setenv("DATABASE_URL", value)
    with pytest.raises(RuntimeError):
        create_pool()
