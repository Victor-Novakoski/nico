import os

import psycopg
import pytest

from nico import create_user as cu
from nico.auth import hash_password, verify_password
from nico.migrate import migrate

URL = os.environ.get("NICO_TEST_DATABASE_URL")
needs_db = pytest.mark.skipif(not URL, reason="NICO_TEST_DATABASE_URL não definida")

PASSWORD = "senha-inventada-1"


def test_correct_password_verifies():
    assert verify_password(PASSWORD, hash_password(PASSWORD))


def test_wrong_password_fails():
    assert not verify_password("outra-senha-9", hash_password(PASSWORD))


def test_salt_differs_each_time():
    a, b = hash_password(PASSWORD), hash_password(PASSWORD)
    assert a != b
    assert verify_password(PASSWORD, a) and verify_password(PASSWORD, b)


def test_params_are_stored_in_hash():
    assert hash_password(PASSWORD).startswith("scrypt$16384$8$1$")


@pytest.mark.parametrize("bad", ["", "lixo", "scrypt$x$8$1$aa$bb", "md5$1$1$1$aa$bb"])
def test_malformed_hash_is_false(bad):
    assert verify_password(PASSWORD, bad) is False


@pytest.fixture
def db():
    with psycopg.connect(URL, autocommit=True) as setup:
        setup.execute("drop schema public cascade")
        setup.execute("create schema public")
    migrate(URL)
    with psycopg.connect(URL, autocommit=True) as c:
        yield c


def _run(monkeypatch, capsys, answers, args=("ana", "Ana Teste")):
    monkeypatch.setenv("DATABASE_URL", URL or "")
    it = iter(answers)
    monkeypatch.setattr(cu.getpass, "getpass", lambda prompt="": next(it))
    code = cu.main(list(args))
    return code, capsys.readouterr()


@needs_db
def test_creates_person_and_user(db, monkeypatch, capsys):
    code, out = _run(monkeypatch, capsys, [PASSWORD, PASSWORD])
    assert code == 0
    assert PASSWORD not in out.out + out.err
    stored = db.execute("select password_hash from app_user where username = 'ana'").fetchone()[0]
    assert verify_password(PASSWORD, stored)
    assert db.execute("select count(*) from person").fetchone()[0] == 1


@needs_db
def test_reuses_existing_person(db, monkeypatch, capsys):
    db.execute("insert into person (name) values ('Ana Teste')")
    code, _ = _run(monkeypatch, capsys, [PASSWORD, PASSWORD])
    assert code == 0
    assert db.execute("select count(*) from person").fetchone()[0] == 1


@needs_db
def test_mismatch_and_short_are_refused(db, monkeypatch, capsys):
    code, out = _run(monkeypatch, capsys, [PASSWORD, "diferente-123"])
    assert code == 1 and "iguais" in out.err
    code, out = _run(monkeypatch, capsys, ["curta", "curta"])
    assert code == 1 and "8 caracteres" in out.err
    assert db.execute("select count(*) from app_user").fetchone()[0] == 0
    assert db.execute("select count(*) from person").fetchone()[0] == 0


@needs_db
def test_duplicate_username_is_refused_without_leaking(db, monkeypatch, capsys):
    _run(monkeypatch, capsys, [PASSWORD, PASSWORD])
    code, out = _run(monkeypatch, capsys, [PASSWORD, PASSWORD])
    assert code == 1 and "já existe" in out.err
    assert PASSWORD not in out.out + out.err


def test_missing_database_url_is_clear(monkeypatch, capsys):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    assert cu.main(["ana", "Ana Teste"]) == 1
    assert "DATABASE_URL" in capsys.readouterr().err


def test_missing_args_shows_usage(capsys):
    assert cu.main(["ana"]) == 1
    assert "Uso:" in capsys.readouterr().err
