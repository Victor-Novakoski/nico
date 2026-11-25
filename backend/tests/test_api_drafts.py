from datetime import date

import psycopg
import pytest

URL = "/api/drafts/parse"
TODAY = date(2026, 11, 25)

# `logged_client` (conftest) já cria e loga a usuária Fulana. Tudo aqui é inventado.


@pytest.fixture(autouse=True)
def _fixed_today(monkeypatch):
    monkeypatch.setattr("nico.routes.drafts.dates.today_sp", lambda: TODAY)


def create_method(client, name, kind, alias=None):
    body = {"name": name, "owner_id": client.get("/api/me").json()["person_id"], "kind": kind}
    if kind == "credito":
        body.update(closing_day=10, due_day=17)
    response = client.post("/api/payment-methods", json=body)
    assert response.status_code == 201
    method = response.json()
    if alias:
        added = client.post(f"/api/payment-methods/{method['id']}/aliases", json={"alias": alias})
        assert added.status_code == 201
    return method


def parse(client, text):
    response = client.post(URL, json={"text": text})
    assert response.status_code == 200
    return response.json()


def test_requires_login(client):
    assert client.post(URL, json={"text": "10 pão"}).status_code == 401


def test_simple_sentence_with_alias(logged_client):
    method = create_method(logged_client, "Cartão Roxo", "credito", alias="roxo")
    body = parse(logged_client, "120 no mercado no roxo 3x")
    assert body["understood"] is True
    assert body["drafts"] == [
        {
            "description": "mercado",
            "amount_cents": 12000,
            "method_id": method["id"],
            "method_type": "credito",
            "purchase_date": "2026-11-25",
            "installments": 3,
            "missing": [],
            "sources": {
                "amount_cents": "frase",
                "description": "frase",
                "method_id": "frase",
                "purchase_date": "padrao",
                "installments": "frase",
            },
        }
    ]


def test_method_name_works_as_alias_and_date_from_phrase(logged_client):
    method = create_method(logged_client, "Cartão Roxo", "credito")
    draft = parse(logged_client, "50 farmácia cartão roxo ontem")["drafts"][0]
    assert draft["method_id"] == method["id"]
    assert draft["purchase_date"] == "2026-11-24"
    assert draft["sources"]["purchase_date"] == "frase"
    assert draft["installments"] == 1
    assert draft["sources"]["installments"] == "padrao"


def test_two_expenses_separated_by_semicolon(logged_client):
    create_method(logged_client, "Cartão Roxo", "credito", alias="roxo")
    pix = create_method(logged_client, "Pix da casa", "pix", alias="pix")
    body = parse(logged_client, "120 mercado no roxo; 15 pão no pix")
    assert body["understood"] is True
    assert [d["amount_cents"] for d in body["drafts"]] == [12000, 1500]
    assert body["drafts"][1]["method_id"] == pix["id"]
    assert body["drafts"][1]["method_type"] == "pix"


def test_unknown_method_is_missing(logged_client):
    body = parse(logged_client, "30 padaria no cartão verde")
    draft = body["drafts"][0]
    assert body["understood"] is True
    assert draft["method_id"] is None
    assert draft["method_type"] is None
    assert "method_id" in draft["missing"]
    assert "card_id" not in draft["missing"]
    assert "method_id" not in draft["sources"]


def test_cash_method_with_installments_is_doubtful(logged_client):
    create_method(logged_client, "Débito do banco", "debito", alias="debito")
    draft = parse(logged_client, "90 sapato no debito 3x")["drafts"][0]
    assert draft["method_type"] == "debito"
    assert draft["installments"] == 1
    assert "installments" in draft["missing"]
    assert draft["sources"]["installments"] == "padrao"


def test_not_understood(logged_client):
    assert parse(logged_client, "comprei umas coisas por aí") == {
        "understood": False,
        "drafts": [],
    }


@pytest.mark.parametrize("text", ["", "   ", "x" * 501])
def test_invalid_text_is_422(logged_client, text):
    assert logged_client.post(URL, json={"text": text}).status_code == 422
    assert logged_client.post(URL, json={}).status_code == 422


def test_writes_nothing(logged_client, auth_env):
    create_method(logged_client, "Cartão Roxo", "credito", alias="roxo")

    def counts():
        with psycopg.connect(auth_env) as conn:
            tables = [
                r[0]
                for r in conn.execute(
                    "select tablename from pg_tables where schemaname = 'public'"
                    " and tablename <> 'schema_migrations' order by 1"
                )
            ]
            return {t: conn.execute(f'select count(*) from "{t}"').fetchone()[0] for t in tables}

    before = counts()
    parse(logged_client, "120 mercado no roxo 2x")
    parse(logged_client, "texto sem valor")
    assert counts() == before
