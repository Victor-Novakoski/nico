import os
import uuid

import psycopg
import pytest
from psycopg import errors

from nico.migrate import migrate

URL = os.environ.get("NICO_TEST_DATABASE_URL")

pytestmark = pytest.mark.skipif(not URL, reason="NICO_TEST_DATABASE_URL não definida")

TABLES = {
    "person",
    "payment_method",
    "payment_method_alias",
    "invoice",
    "purchase",
    "installment",
    "purchase_share",
    "app_user",
    "schema_migrations",
}


@pytest.fixture
def conn(db_url):
    with psycopg.connect(db_url, autocommit=True) as c:
        yield c


def _person(c) -> uuid.UUID:
    return c.execute("insert into person (name) values ('Ana') returning id").fetchone()[0]


def _method(c, person, kind="credito", closing=10, due=17, name=None) -> uuid.UUID:
    return c.execute(
        "insert into payment_method (owner_person_id, name, kind, closing_day, due_day)"
        " values (%s, %s, %s, %s, %s) returning id",
        (person, name or f"m-{uuid.uuid4()}", kind, closing, due),
    ).fetchone()[0]


def _purchase(c, person, method, total=1000, purchase_id=None) -> uuid.UUID:
    pid = purchase_id or uuid.uuid4()
    c.execute(
        "insert into purchase (id, description, total_cents, purchase_date,"
        " payment_method_id, created_by_person_id)"
        " values (%s, 'mercado', %s, '2026-01-05', %s, %s)",
        (pid, total, method, person),
    )
    return pid


def test_migrate_is_idempotent(conn):
    assert migrate(URL) == []
    rows = conn.execute("select name from schema_migrations").fetchall()
    assert rows == [("001_init.sql",)]
    tables = {
        r[0] for r in conn.execute("select tablename from pg_tables where schemaname = 'public'")
    }
    assert tables == TABLES


def test_first_run_reports_applied_file():
    with psycopg.connect(URL, autocommit=True) as setup:
        setup.execute("drop schema public cascade")
        setup.execute("create schema public")
    assert migrate(URL) == ["001_init.sql"]


def test_negative_total_is_rejected(conn):
    p = _person(conn)
    m = _method(conn, p)
    with pytest.raises(errors.CheckViolation):
        _purchase(conn, p, m, total=-1)


def test_credit_requires_both_days(conn):
    p = _person(conn)
    with pytest.raises(errors.CheckViolation):
        _method(conn, p, "credito", closing=None, due=None)
    with pytest.raises(errors.CheckViolation):
        _method(conn, p, "credito", closing=10, due=None)


@pytest.mark.parametrize("kind", ["debito", "pix", "dinheiro"])
def test_cash_kinds_reject_days_and_accept_null(conn, kind):
    p = _person(conn)
    with pytest.raises(errors.CheckViolation):
        _method(conn, p, kind, closing=10, due=17)
    _method(conn, p, kind, closing=None, due=None)


def test_unknown_kind_is_rejected(conn):
    p = _person(conn)
    with pytest.raises(errors.CheckViolation):
        _method(conn, p, "cheque", closing=None, due=None)


def test_alias_is_unique_ignoring_case(conn):
    p = _person(conn)
    m1 = _method(conn, p)
    m2 = _method(conn, p)
    conn.execute(
        "insert into payment_method_alias (payment_method_id, alias) values (%s, 'Roxinho')",
        (m1,),
    )
    with pytest.raises(errors.UniqueViolation):
        conn.execute(
            "insert into payment_method_alias (payment_method_id, alias) values (%s, 'roxinho')",
            (m2,),
        )


def test_invoice_only_for_credit_and_unique_per_month(conn):
    p = _person(conn)
    credit = _method(conn, p)
    debit = _method(conn, p, "debito", None, None)
    sql = (
        "insert into invoice (payment_method_id, year, month, closing_date, due_date)"
        " values (%s, 2026, 2, '2026-02-10', '2026-02-17')"
    )
    with pytest.raises(errors.ForeignKeyViolation):
        conn.execute(sql, (debit,))
    conn.execute(sql, (credit,))
    with pytest.raises(errors.UniqueViolation):
        conn.execute(sql, (credit,))


def test_deleting_purchase_cascades_to_installments_and_shares(conn):
    p = _person(conn)
    m = _method(conn, p)
    inv = conn.execute(
        "insert into invoice (payment_method_id, year, month, closing_date, due_date)"
        " values (%s, 2026, 2, '2026-02-10', '2026-02-17') returning id",
        (m,),
    ).fetchone()[0]
    pid = _purchase(conn, p, m)
    conn.execute(
        "insert into installment (purchase_id, invoice_id, number, amount_cents)"
        " values (%s, %s, 1, 1000)",
        (pid, inv),
    )
    conn.execute(
        "insert into purchase_share (purchase_id, person_id, weight) values (%s, %s, 1)",
        (pid, p),
    )
    with pytest.raises(errors.CheckViolation):
        conn.execute(
            "insert into purchase_share (purchase_id, person_id, weight) values (%s, %s, 0)",
            (pid, _person(conn)),
        )
    conn.execute("delete from purchase where id = %s", (pid,))
    assert conn.execute("select count(*) from installment").fetchone()[0] == 0
    assert conn.execute("select count(*) from purchase_share").fetchone()[0] == 0
    # fatura e pessoa continuam
    assert conn.execute("select count(*) from invoice").fetchone()[0] == 1
    assert conn.execute("select count(*) from person").fetchone()[0] >= 1


def test_default_method_is_nullable_and_cleared_when_method_deleted(conn):
    p = _person(conn)
    m = _method(conn, p, "pix", None, None)
    uid = conn.execute(
        "insert into app_user (person_id, username, password_hash, default_method_id)"
        " values (%s, 'ana', 'hash', %s) returning id",
        (p, m),
    ).fetchone()[0]
    row = conn.execute("select ai_enabled from app_user where id = %s", (uid,)).fetchone()
    assert row == (False,)
    conn.execute("delete from payment_method where id = %s", (m,))
    row = conn.execute("select default_method_id from app_user where id = %s", (uid,)).fetchone()
    assert row == (None,)
    with pytest.raises(errors.UniqueViolation):
        conn.execute(
            "insert into app_user (person_id, username, password_hash) values (%s, 'ana', 'x')",
            (p,),
        )
