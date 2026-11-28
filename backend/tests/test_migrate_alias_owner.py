"""Migração 004: o apelido ganha dono, preenchido a partir do meio. Dados inventados."""

import os
import shutil
from pathlib import Path

import psycopg
import pytest
from psycopg import errors

from nico.migrate import migrate

URL = os.environ.get("NICO_TEST_DATABASE_URL")

pytestmark = pytest.mark.skipif(not URL, reason="NICO_TEST_DATABASE_URL não definida")

MIGRATIONS = Path(__file__).resolve().parents[1] / "migrations"


@pytest.fixture
def conn():
    with psycopg.connect(URL, autocommit=True) as c:
        c.execute("drop schema public cascade")
        c.execute("create schema public")
        yield c


@pytest.fixture
def old_dir(tmp_path):
    for name in ("001_init.sql", "002_grupos.sql", "003_escopo.sql"):
        shutil.copy(MIGRATIONS / name, tmp_path / name)
    return tmp_path


def _person_with_method(c, name) -> tuple[str, str]:
    person = c.execute("insert into person (name) values (%s) returning id", (name,)).fetchone()[0]
    method = c.execute(
        "insert into payment_method (owner_person_id, name, kind) values (%s, 'Pix', 'pix')"
        " returning id",
        (person,),
    ).fetchone()[0]
    return person, method


def test_existing_aliases_get_the_method_owner(conn, old_dir):
    migrate(URL, directory=old_dir)
    ana, ana_pix = _person_with_method(conn, "Ana")
    bia, bia_pix = _person_with_method(conn, "Bia")
    for method, alias in ((ana_pix, "roxo"), (bia_pix, "azul")):
        conn.execute(
            "insert into payment_method_alias (payment_method_id, alias) values (%s, %s)",
            (method, alias),
        )

    assert migrate(URL) == ["004_apelido_por_dono.sql"]

    rows = dict(conn.execute("select alias, owner_person_id from payment_method_alias"))
    assert rows == {"roxo": ana, "azul": bia}
    # Agora a Bia pode usar o mesmo apelido da Ana.
    conn.execute(
        "insert into payment_method_alias (payment_method_id, owner_person_id, alias)"
        " values (%s, %s, 'Roxo')",
        (bia_pix, bia),
    )
    with pytest.raises(errors.NotNullViolation):
        conn.execute(
            "insert into payment_method_alias (payment_method_id, alias) values (%s, 'verde')",
            (ana_pix,),
        )
