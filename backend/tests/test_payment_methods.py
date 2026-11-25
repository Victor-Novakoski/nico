import pytest

URL = "/api/payment-methods"

# `logged_client` (conftest) já cria e loga a usuária Fulana, que é uma pessoa da casa.


def owner_id(client) -> str:
    return client.get("/api/me").json()["person_id"]


def create(client, **fields):
    body = {"name": "Cartão Azul", "owner_id": owner_id(client), "kind": "credito"}
    if body["kind"] == "credito" and "kind" not in fields:
        body.update(closing_day=10, due_day=17)
    body.update(fields)
    return client.post(URL, json=body)


def test_requires_login(client):
    assert client.get(URL).status_code == 401
    assert client.post(URL, json={}).status_code == 401
    assert client.post(f"{URL}/x/aliases", json={"alias": "a"}).status_code == 401


def test_create_credit_and_list(logged_client):
    client = logged_client
    response = create(client)
    assert response.status_code == 201
    created = response.json()
    assert created == {
        "id": created["id"],
        "name": "Cartão Azul",
        "owner_id": owner_id(client),
        "kind": "credito",
        "closing_day": 10,
        "due_day": 17,
        "aliases": [],
    }
    assert client.get(URL).json() == [created]


def test_create_pix_without_days(logged_client):
    response = create(logged_client, name="Pix da casa", kind="pix")
    assert response.status_code == 201
    assert response.json()["closing_day"] is None
    assert response.json()["due_day"] is None


def test_list_sorted_by_name_ignoring_case(logged_client):
    for name in ["beta", "Carteira", "alfa"]:
        create(logged_client, name=name, kind="dinheiro")
    assert [m["name"] for m in logged_client.get(URL).json()] == ["alfa", "beta", "Carteira"]


@pytest.mark.parametrize("days", [{"closing_day": 10}, {"due_day": 17}, {}])
def test_credit_missing_a_day_is_422(logged_client, days):
    response = logged_client.post(
        URL, json={"name": "X", "owner_id": owner_id(logged_client), "kind": "credito", **days}
    )
    assert response.status_code == 422
    assert logged_client.get(URL).json() == []


@pytest.mark.parametrize("day", [0, 32])
def test_credit_day_out_of_range_is_422(logged_client, day):
    assert create(logged_client, closing_day=day).status_code == 422
    assert create(logged_client, due_day=day).status_code == 422


@pytest.mark.parametrize("kind", ["debito", "pix", "dinheiro"])
@pytest.mark.parametrize(
    "days", [{"closing_day": 5}, {"due_day": 5}, {"closing_day": 5, "due_day": 9}]
)
def test_cash_kinds_with_days_are_422(logged_client, kind, days):
    assert create(logged_client, kind=kind, **days).status_code == 422


def test_invalid_kind_and_name_are_422(logged_client):
    assert create(logged_client, kind="cheque").status_code == 422
    assert create(logged_client, name="   ", kind="pix").status_code == 422


def test_unknown_owner_is_422(logged_client):
    response = create(logged_client, kind="pix", owner_id="00000000-0000-0000-0000-000000000000")
    assert response.status_code == 422
    assert "Dono" in response.json()["detail"]


def test_alias_is_saved_normalized(logged_client):
    method = create(logged_client).json()
    response = logged_client.post(f"{URL}/{method['id']}/aliases", json={"alias": "  Cartão AZUL "})
    assert response.status_code == 201
    assert response.json()["aliases"] == ["cartao azul"]
    assert logged_client.get(URL).json()[0]["aliases"] == ["cartao azul"]


def test_aliases_are_ordered(logged_client):
    method = create(logged_client).json()
    for alias in ["zeta", "alfa"]:
        logged_client.post(f"{URL}/{method['id']}/aliases", json={"alias": alias})
    assert logged_client.get(URL).json()[0]["aliases"] == ["alfa", "zeta"]


@pytest.mark.parametrize("second", ["azul", "AZUL", "Ázul"])
def test_duplicate_alias_is_409(logged_client, second):
    first = create(logged_client, name="Um").json()
    other = create(logged_client, name="Dois", kind="pix").json()
    assert (
        logged_client.post(f"{URL}/{first['id']}/aliases", json={"alias": "azul"}).status_code
        == 201
    )
    response = logged_client.post(f"{URL}/{other['id']}/aliases", json={"alias": second})
    assert response.status_code == 409
    assert response.json()["detail"] == "Apelido já usado em outro meio de pagamento"
    by_id = {m["id"]: m for m in logged_client.get(URL).json()}
    assert by_id[other["id"]]["aliases"] == []
    assert by_id[first["id"]]["aliases"] == ["azul"]


def test_duplicate_alias_on_same_method_is_409(logged_client):
    method = create(logged_client).json()
    assert (
        logged_client.post(f"{URL}/{method['id']}/aliases", json={"alias": "azul"}).status_code
        == 201
    )
    assert (
        logged_client.post(f"{URL}/{method['id']}/aliases", json={"alias": "Azul"}).status_code
        == 409
    )


def test_alias_on_unknown_method_is_404(logged_client):
    response = logged_client.post(
        f"{URL}/00000000-0000-0000-0000-000000000000/aliases", json={"alias": "azul"}
    )
    assert response.status_code == 404


@pytest.mark.parametrize("alias", ["", "   ", " ... "])
def test_empty_alias_is_422(logged_client, alias):
    method = create(logged_client).json()
    assert (
        logged_client.post(f"{URL}/{method['id']}/aliases", json={"alias": alias}).status_code
        == 422
    )
