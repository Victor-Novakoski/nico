from datetime import date

import pytest

from nico.ai.cascade import Cascade
from nico.ai.schema import ExtractedItem, Extraction
from nico.routes.drafts import get_cascade

URL = "/api/drafts/parse"
TODAY = date(2026, 11, 25)

# Tudo inventado. `logged_client` (conftest) já cria e loga a usuária Fulana.


@pytest.fixture(autouse=True)
def _fixed_today(monkeypatch):
    monkeypatch.setattr("nico.routes.drafts.dates.today_sp", lambda: TODAY)


class FakeProvider:
    def __init__(self, result):
        self.result = result

    def extract(self, text, context):
        return self.result


@pytest.fixture
def use_ai(logged_client):
    from nico.app import app

    def install(result):
        app.dependency_overrides[get_cascade] = lambda: Cascade([("fake", FakeProvider(result))])

    yield install
    app.dependency_overrides.pop(get_cascade, None)


def create_card(client, name, alias):
    body = {
        "name": name,
        "owner_id": client.get("/api/me").json()["person_id"],
        "kind": "credito",
        "closing_day": 10,
        "due_day": 17,
    }
    method = client.post("/api/payment-methods", json=body).json()
    client.post(f"/api/payment-methods/{method['id']}/aliases", json={"alias": alias})
    return method


def parse(client, text):
    response = client.post(URL, json={"text": text})
    assert response.status_code == 200
    return response.json()


def texts(text, draft):
    return {s["field"]: text[s["start"] : s["end"]] for s in draft["spans"]}


def test_rules_spans_in_two_drafts(logged_client):
    create_card(logged_client, "Cartão Azul", "azul")
    text = "120 no mercado no Azul em 3x; 15 de pão"
    first, second = parse(logged_client, text)["drafts"]
    assert texts(text, first) == {
        "amount_cents": "120",
        "description": "mercado",
        "method_id": "Azul",
        "installments": "3x",
    }
    # Sem meio nem parcelas na frase: só valor e descrição, nas posições do 2º trecho.
    assert texts(text, second) == {"amount_cents": "15", "description": "pão"}


def test_default_method_has_no_span(logged_client):
    card = create_card(logged_client, "Cartão Azul", "azul")
    logged_client.patch("/api/me/settings", json={"default_method_id": card["id"]})
    text = "15 pão"
    [draft] = parse(logged_client, text)["drafts"]
    assert draft["sources"]["method_id"] == "padrao"
    assert set(texts(text, draft)) == {"amount_cents", "description"}


def test_ai_spans_found_by_code(logged_client, use_ai):
    create_card(logged_client, "Cartão Roxo", "roxo")
    logged_client.patch("/api/me/settings", json={"ai_enabled": True})
    text = "paguei o mercado ontem no roxo, 120 reais"
    use_ai(
        Extraction(
            items=[
                ExtractedItem(
                    description="Mercado", amount_text="120 reais", method="roxo", date_text="ontem"
                )
            ]
        )
    )
    [draft] = parse(logged_client, text)["drafts"]
    assert texts(text, draft) == {
        "amount_cents": "120",
        "description": "mercado",
        "method_id": "roxo",
    }


def test_ai_text_not_in_phrase_has_no_span(logged_client, use_ai):
    logged_client.patch("/api/me/settings", json={"ai_enabled": True})
    use_ai(Extraction(items=[ExtractedItem(description="padaria", amount_text="99")]))
    [draft] = parse(logged_client, "paguei o mercado ontem")["drafts"]
    assert draft["amount_cents"] == 9900
    assert draft["spans"] == []
