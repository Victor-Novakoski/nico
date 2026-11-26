from datetime import date

import pytest

from nico.ai.base import AllProvidersFailed, ProviderUnavailable
from nico.ai.cascade import Cascade
from nico.ai.schema import ExtractedItem, Extraction
from nico.routes.drafts import get_cascade

URL = "/api/drafts/parse"
TODAY = date(2026, 11, 25)
# Frase que as regras não entendem (sem valor no começo) e uma que elas resolvem.
HARD = "paguei o mercado ontem no roxo"
SIMPLE = "15 pão"


class FakeProvider:
    def __init__(self, result):
        self.result = result
        self.calls = 0

    def extract(self, text, context):
        self.calls += 1
        if isinstance(self.result, BaseException):
            raise self.result
        return self.result


@pytest.fixture(autouse=True)
def _fixed_today(monkeypatch):
    monkeypatch.setattr("nico.routes.drafts.dates.today_sp", lambda: TODAY)


@pytest.fixture
def use_ai(logged_client):
    """Instala uma cascata falsa; devolve o provedor falso para contar as chamadas."""
    from nico.app import app

    def install(result, name="fake"):
        provider = FakeProvider(result)
        app.dependency_overrides[get_cascade] = lambda: Cascade([(name, provider)])
        return provider

    yield install
    app.dependency_overrides.pop(get_cascade, None)


def set_ai(client, enabled):
    response = client.patch("/api/me/settings", json={"ai_enabled": enabled})
    assert response.status_code == 200


def create_card(client):
    body = {
        "name": "Cartão Roxo",
        "owner_id": client.get("/api/me").json()["person_id"],
        "kind": "credito",
        "closing_day": 10,
        "due_day": 17,
    }
    method = client.post("/api/payment-methods", json=body).json()
    client.post(f"/api/payment-methods/{method['id']}/aliases", json={"alias": "roxo"})
    return method


def parse(client, text):
    response = client.post(URL, json={"text": text})
    assert response.status_code == 200
    return response.json()


GOOD = Extraction(
    items=[
        ExtractedItem(
            description="mercado", amount_text="120 reais", method="roxo", date_text="ontem"
        )
    ]
)


def test_rules_resolve_without_calling_ai(logged_client, use_ai):
    set_ai(logged_client, True)
    provider = use_ai(GOOD)
    body = parse(logged_client, SIMPLE)
    assert body["understood"] is True
    assert body["origin"] == "rules"
    assert body["fallback"] is None
    assert provider.calls == 0


def test_ai_off_never_calls_ai(logged_client, use_ai):
    provider = use_ai(GOOD)
    body = parse(logged_client, HARD)
    assert body == {"understood": False, "drafts": [], "origin": None, "fallback": "form"}
    assert provider.calls == 0


def test_ai_on_uses_provider_when_rules_fail(logged_client, use_ai):
    card = create_card(logged_client)
    set_ai(logged_client, True)
    provider = use_ai(GOOD, name="fakeprov")
    body = parse(logged_client, HARD)
    assert provider.calls == 1
    assert body["understood"] is True
    assert body["origin"] == "fakeprov"
    assert body["fallback"] is None
    [draft] = body["drafts"]
    assert draft["amount_cents"] == 12000
    assert draft["method_id"] == card["id"]
    assert draft["method_type"] == "credito"
    assert draft["purchase_date"] == "2026-11-24"
    assert draft["person_id"] == logged_client.get("/api/me").json()["person_id"]
    assert draft["sources"]["amount_cents"] == "ia"
    assert draft["sources"]["person_id"] == "padrao"
    assert draft["missing"] == []


def test_ai_draft_uses_default_method(logged_client, use_ai):
    card = create_card(logged_client)
    logged_client.patch("/api/me/settings", json={"default_method_id": card["id"]})
    set_ai(logged_client, True)
    use_ai(Extraction(items=[ExtractedItem(description="pão", amount_text="15")]))
    [draft] = parse(logged_client, HARD)["drafts"]
    assert draft["method_id"] == card["id"]
    assert draft["sources"]["method_id"] == "padrao"
    assert "method_id" not in draft["missing"]


def test_all_providers_fail_falls_back_to_form(logged_client, use_ai):
    set_ai(logged_client, True)
    provider = use_ai(ProviderUnavailable())
    body = parse(logged_client, HARD)
    assert provider.calls == 1
    assert body == {"understood": False, "drafts": [], "origin": None, "fallback": "form"}


def test_no_cascade_configured_falls_back_to_form(logged_client):
    set_ai(logged_client, True)
    from nico.app import app

    app.dependency_overrides[get_cascade] = lambda: None
    try:
        assert parse(logged_client, HARD)["fallback"] == "form"
    finally:
        app.dependency_overrides.pop(get_cascade, None)


def test_empty_extraction_falls_back_to_form(logged_client, use_ai):
    set_ai(logged_client, True)
    use_ai(Extraction(items=[]))
    assert parse(logged_client, HARD)["fallback"] == "form"


def test_ids_outside_closed_list_are_rejected(logged_client, use_ai):
    create_card(logged_client)
    set_ai(logged_client, True)
    bad = Extraction(
        items=[
            ExtractedItem(
                description="mercado",
                amount_text="120",
                method="00000000-0000-0000-0000-000000000000",
                person="Beltrana",
            )
        ]
    )
    use_ai(bad)
    me = logged_client.get("/api/me").json()["person_id"]
    [draft] = parse(logged_client, HARD)["drafts"]
    assert draft["method_id"] is None
    assert "method_id" in draft["missing"]
    assert draft["person_id"] == me  # pessoa fora da lista: entra quem lançou (padrão)
    assert draft["sources"]["person_id"] == "padrao"


def test_cash_method_does_not_install(logged_client, use_ai):
    logged_client.post(
        "/api/payment-methods",
        json={
            "name": "Pix",
            "owner_id": logged_client.get("/api/me").json()["person_id"],
            "kind": "pix",
        },
    )
    set_ai(logged_client, True)
    use_ai(
        Extraction(
            items=[ExtractedItem(description="x", amount_text="10", method="pix", installments=3)]
        )
    )
    [draft] = parse(logged_client, HARD)["drafts"]
    assert draft["installments"] == 1
    assert "installments" in draft["missing"]


def test_all_failed_exception_type_is_handled(logged_client):
    set_ai(logged_client, True)
    from nico.app import app

    class Boom:
        def extract(self, text, context):
            raise AllProvidersFailed([("a", "x")])

    app.dependency_overrides[get_cascade] = lambda: Cascade([("a", Boom())])
    try:
        assert parse(logged_client, HARD)["fallback"] == "form"
    finally:
        app.dependency_overrides.pop(get_cascade, None)
