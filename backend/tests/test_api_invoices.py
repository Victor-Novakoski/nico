from datetime import date
from uuid import UUID, uuid4

import psycopg

from nico.purchases import create_purchase

URL = "/api/payment-methods"


def me(client) -> str:
    return client.get("/api/me").json()["person_id"]


def new_person(client, name="Beltrana") -> str:
    return client.post("/api/people", json={"name": name}).json()["id"]


def new_method(client, **fields) -> str:
    body = {
        "name": "Cartão Azul",
        "owner_id": me(client),
        "kind": "credito",
        "closing_day": 10,
        "due_day": 17,
    }
    body.update(fields)
    response = client.post(URL, json=body)
    assert response.status_code == 201
    return response.json()["id"]


def buy(db_url, method_id, *, created_by, shares=None, **fields):
    args = {
        "id": uuid4(),
        "payment_method_id": UUID(method_id),
        "description": "Compra",
        "total_cents": 10000,
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
    assert client.get(f"{URL}/{uuid4()}/invoices/2026/1").status_code == 401
    assert client.get(f"{URL}/{uuid4()}/invoices/current").status_code == 401


def test_installments_split_between_two_people(logged_client, db_url):
    client = logged_client
    a, b = me(client), new_person(client)
    method = new_method(client)
    buy(
        db_url,
        method,
        description="Geladeira",
        total_cents=10000,
        installments=3,
        created_by=a,
        shares={a: 1, b: 1},
    )
    expected = [(1, 3334), (2, 3333), (3, 3333)]
    for (number, amount), month in zip(expected, (1, 2, 3), strict=True):
        data = client.get(f"{URL}/{method}/invoices/2026/{month}").json()
        assert data["exists"] is True
        assert data["total_cents"] == amount
        assert data["pending_count"] == 1
        assert data["due_date"] == f"2026-{month:02d}-17"
        (item,) = data["items"]
        assert item["description"] == "Geladeira"
        assert (item["installment_number"], item["installments"]) == (number, 3)
        assert item["amount_cents"] == amount
        assert item["status"] == "pendente"
        assert item["shares"] == {a: 1, b: 1}
        assert set(data["per_person"]) == {a, b}
        assert sum(data["per_person"].values()) == data["total_cents"]


def test_odd_split_three_people_sums_to_total(logged_client, db_url):
    client = logged_client
    a, b, c = me(client), new_person(client, "Beltrana"), new_person(client, "Ciclano")
    method = new_method(client)
    buy(db_url, method, total_cents=100, created_by=a, shares={a: 1, b: 1, c: 1})
    data = client.get(f"{URL}/{method}/invoices/2026/1").json()
    assert data["total_cents"] == 100
    assert sorted(data["per_person"].values()) == [33, 33, 34]
    assert sum(data["per_person"].values()) == 100


def test_pending_count_and_item_order(logged_client, db_url):
    client = logged_client
    a = me(client)
    method = new_method(client)
    common = {"created_by": a, "total_cents": 1000}
    buy(db_url, method, description="Zebra", purchase_date=date(2026, 1, 3), **common)
    buy(db_url, method, description="Abacate", purchase_date=date(2026, 1, 4), **common)
    buy(
        db_url,
        method,
        description="Bolo",
        purchase_date=date(2026, 1, 3),
        status="conferido",
        **common,
    )
    data = client.get(f"{URL}/{method}/invoices/2026/1").json()
    assert [i["description"] for i in data["items"]] == ["Bolo", "Zebra", "Abacate"]
    assert data["pending_count"] == 2
    assert data["total_cents"] == 3000
    assert data["per_person"] == {a: 3000}


def test_stored_dates_win(logged_client, db_url):
    client = logged_client
    method = new_method(client)
    buy(db_url, method, created_by=me(client))
    with psycopg.connect(db_url) as conn:
        conn.execute(
            "update invoice set closing_date = '2025-12-01', due_date = '2025-12-08'"
            " where payment_method_id = %s",
            (method,),
        )
    data = client.get(f"{URL}/{method}/invoices/2026/1").json()
    assert data["closing_date"] == "2025-12-01"
    assert data["due_date"] == "2025-12-08"


def test_empty_month_has_computed_dates(logged_client):
    client = logged_client
    method = new_method(client)
    data = client.get(f"{URL}/{method}/invoices/2026/5").json()
    assert data == {
        "payment_method_id": method,
        "year": 2026,
        "month": 5,
        "closing_date": "2026-05-10",
        "due_date": "2026-05-17",
        "exists": False,
        "total_cents": 0,
        "per_person": {},
        "pending_count": 0,
        "items": [],
    }


def test_empty_month_when_due_is_next_month(logged_client):
    client = logged_client
    method = new_method(client, closing_day=25, due_day=5)
    data = client.get(f"{URL}/{method}/invoices/2026/1").json()
    assert data["closing_date"] == "2025-12-25"
    assert data["due_date"] == "2026-01-05"
    assert data["exists"] is False


def test_current_invoice(logged_client, db_url, monkeypatch):
    client = logged_client
    method = new_method(client)
    buy(db_url, method, created_by=me(client), purchase_date=date(2026, 3, 20))
    monkeypatch.setattr("nico.routes.invoices.dates.today_sp", lambda: date(2026, 3, 20))
    data = client.get(f"{URL}/{method}/invoices/current").json()
    assert (data["year"], data["month"]) == (2026, 4)
    assert data["exists"] is True
    assert data["total_cents"] == 10000
    monkeypatch.setattr("nico.routes.invoices.dates.today_sp", lambda: date(2026, 3, 5))
    data = client.get(f"{URL}/{method}/invoices/current").json()
    assert (data["year"], data["month"]) == (2026, 3)
    assert data["exists"] is False


def test_cash_method_is_422(logged_client):
    client = logged_client
    for kind in ("debito", "pix", "dinheiro"):
        method = new_method(client, kind=kind, name=kind, closing_day=None, due_day=None)
        for path in ("2026/1", "current"):
            response = client.get(f"{URL}/{method}/invoices/{path}")
            assert response.status_code == 422
            assert response.json()["detail"] == "Só cartão de crédito tem fatura"


def test_unknown_method_is_404(logged_client):
    for path in ("2026/1", "current"):
        assert logged_client.get(f"{URL}/{uuid4()}/invoices/{path}").status_code == 404


def test_month_out_of_range_is_422(logged_client):
    method = new_method(logged_client)
    assert logged_client.get(f"{URL}/{method}/invoices/2026/13").status_code == 422
    assert logged_client.get(f"{URL}/{method}/invoices/2026/0").status_code == 422
