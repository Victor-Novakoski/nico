from datetime import date
from uuid import uuid4

import psycopg
import pytest

from nico.purchases import create_purchase, get_purchase


@pytest.fixture
def conn(db_url):
    with psycopg.connect(db_url) as c:
        yield c


def _person(conn, name):
    return conn.execute("insert into person (name) values (%s) returning id", (name,)).fetchone()[0]


def _credit(conn, owner, closing=25, due=5):
    return conn.execute(
        "insert into payment_method (owner_person_id, name, kind, closing_day, due_day)"
        " values (%s, 'Cartão X', 'credito', %s, %s) returning id",
        (owner, closing, due),
    ).fetchone()[0]


def _debit(conn, owner):
    return conn.execute(
        "insert into payment_method (owner_person_id, name, kind) values (%s, 'Débito', 'debito')"
        " returning id",
        (owner,),
    ).fetchone()[0]


def _count(conn, table):
    return conn.execute(f"select count(*) from {table}").fetchone()[0]


def _buy(conn, method, person, **kw):
    args = dict(
        id=uuid4(),
        payment_method_id=method,
        description="Compra inventada",
        total_cents=10000,
        purchase_date=date(2026, 11, 28),
        installments=1,
        created_by_person_id=person,
    )
    args.update(kw)
    return create_purchase(conn, **args)


def test_credit_3x_crossing_the_year(conn):
    fulana = _person(conn, "Fulana")
    card = _credit(conn, fulana, closing=25, due=5)
    pid = _buy(conn, card, fulana, total_cents=10000, installments=3)
    p = get_purchase(conn, pid)
    rows = p["installments_list"]
    # compra em 28/11, depois do fechamento do dia 25: primeira fatura vence em 05/01/2027
    assert [(r["year"], r["month"]) for r in rows] == [(2027, 1), (2027, 2), (2027, 3)]
    assert [r["due_date"] for r in rows] == [date(2027, 1, 5), date(2027, 2, 5), date(2027, 3, 5)]
    assert [r["closing_date"] for r in rows] == [
        date(2026, 12, 25),
        date(2027, 1, 25),
        date(2027, 2, 25),
    ]
    assert [r["amount_cents"] for r in rows] == [3334, 3333, 3333]
    assert sum(r["amount_cents"] for r in rows) == 10000
    assert [r["number"] for r in rows] == [1, 2, 3]


def test_fifty_fifty_share(conn):
    fulana = _person(conn, "Fulana")
    beltrano = _person(conn, "Beltrano")
    card = _credit(conn, fulana)
    pid = _buy(conn, card, fulana, shares={fulana: 1, beltrano: 1})
    assert get_purchase(conn, pid)["shares"] == {fulana: 1, beltrano: 1}


def test_resend_same_id_does_not_duplicate(conn):
    fulana = _person(conn, "Fulana")
    card = _credit(conn, fulana)
    pid = uuid4()
    assert _buy(conn, card, fulana, id=pid, installments=2) == pid
    assert _buy(conn, card, fulana, id=pid, installments=2) == pid
    assert _count(conn, "purchase") == 1
    assert _count(conn, "installment") == 2
    assert _count(conn, "purchase_share") == 1
    assert _count(conn, "invoice") == 2


def test_existing_invoice_keeps_stored_dates(conn):
    fulana = _person(conn, "Fulana")
    card = _credit(conn, fulana, closing=25, due=5)
    old_id = conn.execute(
        "insert into invoice (payment_method_id, year, month, closing_date, due_date)"
        " values (%s, 2027, 1, '2026-12-20', '2027-01-02') returning id",
        (card,),
    ).fetchone()[0]
    pid = _buy(conn, card, fulana, installments=1)
    row = get_purchase(conn, pid)["installments_list"][0]
    assert row["invoice_id"] == old_id
    assert row["closing_date"] == date(2026, 12, 20)
    assert row["due_date"] == date(2027, 1, 2)
    assert _count(conn, "invoice") == 1


def test_debit_has_no_invoice_or_installments(conn):
    fulana = _person(conn, "Fulana")
    pid = _buy(conn, _debit(conn, fulana), fulana)
    p = get_purchase(conn, pid)
    assert p["installments_list"] == []
    assert _count(conn, "invoice") == 0
    assert _count(conn, "installment") == 0


def test_debit_with_installments_is_refused(conn):
    fulana = _person(conn, "Fulana")
    with pytest.raises(ValueError):
        _buy(conn, _debit(conn, fulana), fulana, installments=3)
    assert _count(conn, "purchase") == 0
    assert _count(conn, "invoice") == 0


def test_empty_shares_go_to_who_entered_not_card_owner(conn):
    fulana = _person(conn, "Fulana")
    beltrano = _person(conn, "Beltrano")
    card = _credit(conn, beltrano)
    pid = _buy(conn, card, fulana)
    assert get_purchase(conn, pid)["shares"] == {fulana: 1}


def test_unknown_payment_method_is_refused(conn):
    fulana = _person(conn, "Fulana")
    with pytest.raises(ValueError):
        _buy(conn, uuid4(), fulana)
    assert _count(conn, "purchase") == 0


@pytest.mark.parametrize(
    "kw",
    [
        {"total_cents": -1},
        {"total_cents": True},
        {"installments": 0},
        {"status": "outro"},
        {"shares": {"x": 0}},
    ],
)
def test_invalid_arguments_are_refused(conn, kw):
    fulana = _person(conn, "Fulana")
    with pytest.raises(ValueError):
        _buy(conn, _credit(conn, fulana), fulana, **kw)
    assert _count(conn, "purchase") == 0
