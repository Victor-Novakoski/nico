"""Gasto de grupo pela API: lançar, divisão padrão e quem pode alterar (decisão 013)."""

import uuid

import psycopg
from test_api_purchases import body, make_group, make_method
from test_isolation import PASSWORD, _login, _make_person

from nico.app import app

URL = "/api/purchases"


def _add_member(db_url, group_id, person_id) -> None:
    with psycopg.connect(db_url) as conn:
        conn.execute(
            "insert into group_member (group_id, person_id, role) values (%s, %s, 'membro')",
            (group_id, person_id),
        )


def _shares(client, purchase_id) -> dict[str, int]:
    data = client.get(f"{URL}/{purchase_id}").json()
    return {s["person_id"]: s["weight"] for s in data["shares"]}


def _setup(logged_client, db_url):
    """Fulana (logada) e Caio no mesmo grupo; Duda fora de qualquer grupo dela."""
    group = make_group(db_url, logged_client)
    caio = _make_person(db_url, "Caio")
    _add_member(db_url, group, caio)
    duda = _make_person(db_url, "Duda")
    method = make_method(logged_client)
    return group, caio, duda, method


def _login_as(name):
    c = _login(app, name)
    assert PASSWORD
    return c


def test_launch_in_group_splits_equally(logged_client, db_url):
    group, caio, _, method = _setup(logged_client, db_url)
    me = logged_client.get("/api/me").json()["person_id"]
    response = logged_client.post(URL, json=body(method, group_id=group))
    assert response.status_code == 201, response.text
    assert response.json()["group_id"] == group
    assert _shares(logged_client, response.json()["id"]) == {me: 1, caio: 1}


def test_launch_in_group_with_explicit_shares(logged_client, db_url):
    group, caio, _, method = _setup(logged_client, db_url)
    shares = [{"person_id": caio, "weight": 3}]
    response = logged_client.post(URL, json=body(method, group_id=group, shares=shares))
    assert response.status_code == 201, response.text
    assert _shares(logged_client, response.json()["id"]) == {caio: 3}


def test_shares_with_stranger_is_422(logged_client, db_url):
    group, _, duda, method = _setup(logged_client, db_url)
    shares = [{"person_id": duda, "weight": 1}]
    response = logged_client.post(URL, json=body(method, group_id=group, shares=shares))
    assert response.status_code == 422


def test_foreign_group_is_404(logged_client, db_url):
    _, _, _, method = _setup(logged_client, db_url)
    with psycopg.connect(db_url) as conn:
        owner = _make_person(db_url, "Bia")
        foreign = conn.execute(
            "insert into expense_group (name, created_by_person_id) values ('B', %s) returning id",
            (owner,),
        ).fetchone()[0]
        conn.execute(
            "insert into group_member (group_id, person_id, role) values (%s, %s, 'dono')",
            (foreign, owner),
        )
    response = logged_client.post(URL, json=body(method, group_id=str(foreign)))
    assert response.status_code == 404


def test_member_who_did_not_launch_cannot_patch_or_delete(logged_client, db_url):
    group, _, _, method = _setup(logged_client, db_url)
    created = logged_client.post(URL, json=body(method, group_id=group)).json()
    caio = _login_as("Caio")
    assert caio.get(f"{URL}/{created['id']}").status_code == 200
    assert caio.patch(f"{URL}/{created['id']}", json={"description": "X"}).status_code == 404
    assert caio.delete(f"{URL}/{created['id']}").status_code == 404
    assert logged_client.get(f"{URL}/{created['id']}").json()["description"] == "Mercado"


def test_patch_moves_to_group_and_back(logged_client, db_url):
    group, caio, _, method = _setup(logged_client, db_url)
    me = logged_client.get("/api/me").json()["person_id"]
    created = logged_client.post(URL, json=body(method)).json()
    assert created["group_id"] is None
    assert _shares(logged_client, created["id"]) == {me: 1}

    moved = logged_client.patch(f"{URL}/{created['id']}", json={"group_id": group})
    assert moved.status_code == 200, moved.text
    assert moved.json()["group_id"] == group
    assert _shares(logged_client, created["id"]) == {me: 1, caio: 1}

    back = logged_client.patch(f"{URL}/{created['id']}", json={"group_id": None})
    assert back.status_code == 200, back.text
    assert back.json()["group_id"] is None
    assert _shares(logged_client, created["id"]) == {me: 1}


def test_patch_to_foreign_group_is_404_and_stranger_share_is_422(logged_client, db_url):
    group, _, duda, method = _setup(logged_client, db_url)
    created = logged_client.post(URL, json=body(method)).json()
    url = f"{URL}/{created['id']}"
    assert logged_client.patch(url, json={"group_id": str(uuid.uuid4())}).status_code == 404
    shares = [{"person_id": duda, "weight": 1}]
    response = logged_client.patch(url, json={"group_id": group, "shares": shares})
    assert response.status_code == 422
    assert logged_client.get(url).json()["group_id"] is None


def test_only_who_launched_with_own_method_moves_scope(logged_client, db_url):
    """O dono do meio que não lançou não tira a compra do grupo de quem lançou."""
    group, caio, _, method = _setup(logged_client, db_url)
    created = logged_client.post(URL, json=body(method, group_id=group)).json()
    with psycopg.connect(db_url) as conn:
        conn.execute(
            "update purchase set created_by_person_id = %s where id = %s", (caio, created["id"])
        )
    response = logged_client.patch(f"{URL}/{created['id']}", json={"group_id": None})
    assert response.status_code == 404
    assert logged_client.get(f"{URL}/{created['id']}").json()["group_id"] == group
