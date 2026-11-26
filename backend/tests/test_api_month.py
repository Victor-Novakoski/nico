from datetime import date
from uuid import UUID, uuid4

import psycopg

from nico.purchases import create_purchase


def me(client) -> str:
    return client.get("/api/me").json()["person_id"]


def new_person(client, name="Beltrana") -> str:
    return client.post("/api/people", json={"name": name}).json()["id"]


def new_method(client, kind="debito", **fields) -> str:
    body = {"name": f"Meio {kind}", "owner_id": me(client), "kind": kind}
    if kind == "credito":
        body.update(closing_day=10, due_day=17)
    body.update(fields)
    response = client.post("/api/payment-methods", json=body)
    assert response.status_code == 201
    return response.json()["id"]


def buy(db_url, method_id, *, created_by, shares=None, **fields):
    args = {
        "id": uuid4(),
        "payment_method_id": UUID(method_id),
        "description": "Compra",
        "total_cents": 1000,
        "purchase_date": date(2026, 1, 5),
        "installments": 1,
        "created_by_person_id": UUID(created_by),
        "shares": {UUID(k): v for k, v in (shares or {}).items()},
    }
    args.update(fields)
    with psycopg.connect(db_url) as conn:
        create_purchase(conn, **args)
    return args["id"]


def test_requires_login(client):
    assert client.get("/api/months/2026/1/cash").status_code == 401


def test_invalid_month_is_422(logged_client):
    for path in ("2026/0/cash", "2026/13/cash", "1999/1/cash"):
        assert logged_client.get(f"/api/months/{path}").status_code == 422


def test_empty_month(logged_client):
    data = logged_client.get("/api/months/2026/1/cash").json()
    assert data["total_cents"] == 0
    assert data["per_person"] == {}
    assert data["pending_count"] == 0
    assert data["items"] == []


def test_cash_purchases_split_between_people_in_two_months(logged_client, db_url):
    client = logged_client
    a, b = me(client), new_person(client)
    debit, pix = new_method(client, "debito"), new_method(client, "pix")
    cash = new_method(client, "dinheiro")
    buy(db_url, debit, created_by=a, total_cents=1000, purchase_date=date(2026, 1, 31))
    buy(db_url, pix, created_by=a, total_cents=101, shares={a: 1, b: 1})
    buy(db_url, cash, created_by=b, total_cents=500, shares={b: 1}, status="conferido")
    buy(db_url, debit, created_by=a, total_cents=700, purchase_date=date(2026, 2, 1))
    jan = client.get("/api/months/2026/1/cash").json()
    assert jan["total_cents"] == 1601
    assert len(jan["items"]) == 3
    assert jan["pending_count"] == 2
    assert set(jan["per_person"]) == {a, b}
    assert sum(jan["per_person"].values()) == jan["total_cents"]
    assert jan["per_person"][b] in (550, 551)
    feb = client.get("/api/months/2026/2/cash").json()
    assert feb["total_cents"] == 700
    assert feb["per_person"] == {a: 700}
    assert client.get("/api/months/2026/3/cash").json()["items"] == []


def test_credit_purchases_are_excluded(logged_client, db_url):
    client = logged_client
    a = me(client)
    card = new_method(client, "credito")
    debit = new_method(client, "debito")
    buy(db_url, card, created_by=a, total_cents=9999)
    buy(db_url, debit, created_by=a, total_cents=300)
    data = client.get("/api/months/2026/1/cash").json()
    assert data["total_cents"] == 300
    assert data["per_person"] == {a: 300}
    assert len(data["items"]) == 1
