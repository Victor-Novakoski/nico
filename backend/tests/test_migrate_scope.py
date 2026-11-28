import os
import shutil
from pathlib import Path

import psycopg
import pytest

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
    for name in ("001_init.sql", "002_grupos.sql"):
        shutil.copy(MIGRATIONS / name, tmp_path / name)
    return tmp_path


def _person(c, name) -> str:
    return c.execute("insert into person (name) values (%s) returning id", (name,)).fetchone()[0]


def _method(c, person) -> str:
    return c.execute(
        "insert into payment_method (owner_person_id, name, kind) values (%s, 'Pix', 'pix')"
        " returning id",
        (person,),
    ).fetchone()[0]


def _purchase(c, creator, method, desc, shares=()) -> str:
    pid = c.execute(
        "insert into purchase (id, description, total_cents, purchase_date,"
        " payment_method_id, created_by_person_id)"
        " values (gen_random_uuid(), %s, 1000, '2026-01-05', %s, %s) returning id",
        (desc, method, creator),
    ).fetchone()[0]
    for person in shares:
        c.execute(
            "insert into purchase_share (purchase_id, person_id, weight) values (%s, %s, 1)",
            (pid, person),
        )
    return pid


def _groups(c):
    return c.execute("select id, name, created_by_person_id from expense_group").fetchall()


def test_existing_data_moves_to_home_group(conn, old_dir):
    migrate(URL, directory=old_dir)
    ana = _person(conn, "Ana")
    bia = _person(conn, "Bia")
    caio = _person(conn, "Caio")
    for person, username in ((bia, "bia"), (caio, "caio")):
        conn.execute(
            "insert into app_user (person_id, username, password_hash) values (%s, %s, 'x')",
            (person, username),
        )
    method = _method(conn, ana)
    split = _purchase(conn, ana, method, "dividida", [ana, bia])
    single = _purchase(conn, bia, method, "só dela", [bia])
    bare = _purchase(conn, caio, method, "sem partes")
    before = conn.execute("select count(*) from purchase").fetchone()[0]

    assert migrate(URL)[0] == "003_escopo.sql"

    groups = _groups(conn)
    assert len(groups) == 1
    group_id, name, creator = groups[0]
    assert name == "Casa"
    assert creator == bia  # menor username entre os app_user
    roles = dict(
        conn.execute("select person_id, role from group_member where group_id = %s", (group_id,))
    )
    assert roles == {bia: "dono", ana: "membro", caio: "membro"}

    scopes = dict(conn.execute("select id, group_id from purchase"))
    assert scopes == {split: group_id, single: None, bare: None}
    assert conn.execute("select count(*) from purchase").fetchone()[0] == before
    nulls = conn.execute(
        "select count(*) from purchase where created_by_person_id is null"
    ).fetchone()[0]
    assert nulls == 0


def test_owner_without_app_user_is_lowest_id(conn, old_dir):
    migrate(URL, directory=old_dir)
    a = _person(conn, "Ana")
    b = _person(conn, "Bia")
    migrate(URL)
    ((_, _, creator),) = _groups(conn)
    assert str(creator) == min(str(a), str(b))


def test_empty_database_creates_no_group(conn):
    assert "003_escopo.sql" in migrate(URL)
    assert _groups(conn) == []


def test_single_person_creates_no_group(conn, old_dir):
    migrate(URL, directory=old_dir)
    ana = _person(conn, "Ana")
    _purchase(conn, ana, _method(conn, ana), "sozinha", [ana])
    migrate(URL)
    assert _groups(conn) == []
    assert conn.execute("select count(*) from purchase where group_id is null").fetchone()[0] == 1
