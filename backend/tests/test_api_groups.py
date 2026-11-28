"""API de grupos (decisão 013). Dados inventados."""

import uuid
from types import SimpleNamespace

import psycopg
import pytest
from fastapi.testclient import TestClient

from nico.auth import hash_password

PASSWORD = "senha-inventada-9"


def _make_user(db_url, name: str) -> str:
    with psycopg.connect(db_url) as conn:
        person_id = conn.execute(
            "insert into person (name) values (%s) returning id", (name,)
        ).fetchone()[0]
        conn.execute(
            "insert into app_user (person_id, username, password_hash) values (%s, %s, %s)",
            (person_id, name.lower(), hash_password(PASSWORD)),
        )
    return str(person_id)


def _login(app, name: str) -> TestClient:
    c = TestClient(app, base_url="https://testserver")
    assert (
        c.post("/api/login", json={"username": name.lower(), "password": PASSWORD}).status_code
        == 200
    )
    return c


@pytest.fixture
def world(client, db_url):
    from nico.app import app

    ids = {n: _make_user(db_url, n) for n in ("Ana", "Bia", "Caio")}
    c = {n: _login(app, n) for n in ids}
    return SimpleNamespace(db=db_url, ids=ids, c=c)


def _create(client, name="Casa") -> str:
    response = client.post("/api/groups", json={"name": name})
    assert response.status_code == 201, response.text
    return response.json()["id"]


def _join(db_url, group_id, person_id):
    with psycopg.connect(db_url) as conn:
        conn.execute(
            "insert into group_member (group_id, person_id, role) values (%s, %s, 'membro')",
            (group_id, person_id),
        )


def _group_purchase(w, group_id, payer: str, total: int, shares: dict[str, int]):
    """Compra do grupo paga pelo meio de `payer`, direto no banco."""
    with psycopg.connect(w.db) as conn:
        method = conn.execute(
            "insert into payment_method (name, owner_person_id, kind) values ('Pix', %s, 'pix')"
            " returning id",
            (w.ids[payer],),
        ).fetchone()[0]
        purchase = uuid.uuid4()
        conn.execute(
            "insert into purchase (id, description, total_cents, purchase_date, payment_method_id,"
            " created_by_person_id, group_id) values (%s, 'Mercado', %s, '2026-03-05', %s, %s, %s)",
            (purchase, total, method, w.ids[payer], group_id),
        )
        for name, weight in shares.items():
            conn.execute(
                "insert into purchase_share (purchase_id, person_id, weight) values (%s, %s, %s)",
                (purchase, w.ids[name], weight),
            )


def test_create_makes_creator_owner(world):
    response = world.c["Ana"].post("/api/groups", json={"name": "  Casa  "})
    assert response.status_code == 201
    body = response.json()
    assert body["name"] == "Casa"
    assert body["role"] == "dono"
    assert body["members"] == [{"id": world.ids["Ana"], "name": "Ana", "role": "dono"}]


def test_create_rejects_empty_name_and_extra_fields(world):
    assert world.c["Ana"].post("/api/groups", json={"name": "  "}).status_code == 422
    assert world.c["Ana"].post("/api/groups", json={"name": "A", "x": 1}).status_code == 422


def test_list_only_mine(world):
    mine = _create(world.c["Ana"], "Casa")
    _create(world.c["Bia"], "Viagem")
    listed = world.c["Ana"].get("/api/groups").json()
    assert [g["id"] for g in listed] == [mine]


def test_non_member_gets_404(world):
    group = _create(world.c["Ana"])
    other = world.c["Bia"]
    assert other.get(f"/api/groups/{group}").status_code == 404
    assert other.patch(f"/api/groups/{group}", json={"name": "X"}).status_code == 404
    assert other.post(f"/api/groups/{group}/people", json={"name": "Duda"}).status_code == 404
    assert other.delete(f"/api/groups/{group}/members/me").status_code == 404


def test_get_shows_members_with_name_and_role_only(world):
    group = _create(world.c["Ana"])
    _join(world.db, group, world.ids["Bia"])
    body = world.c["Bia"].get(f"/api/groups/{group}").json()
    assert {m["name"]: m["role"] for m in body["members"]} == {"Ana": "dono", "Bia": "membro"}
    assert all(set(m) == {"id", "name", "role"} for m in body["members"])


def test_rename_by_owner_and_refused_for_member(world):
    group = _create(world.c["Ana"])
    _join(world.db, group, world.ids["Bia"])
    assert world.c["Bia"].patch(f"/api/groups/{group}", json={"name": "X"}).status_code == 403
    response = world.c["Ana"].patch(f"/api/groups/{group}", json={"name": "Apê"})
    assert response.status_code == 200
    assert response.json()["name"] == "Apê"


def test_add_person_without_login(world):
    group = _create(world.c["Ana"])
    response = world.c["Ana"].post(f"/api/groups/{group}/people", json={"name": "Dona Lia"})
    assert response.status_code == 201
    person_id = response.json()["id"]
    members = world.c["Ana"].get(f"/api/groups/{group}").json()["members"]
    assert {"id": person_id, "name": "Dona Lia", "role": "membro"} in members
    with psycopg.connect(world.db) as conn:
        count = conn.execute("select count(*) from app_user where person_id = %s", (person_id,))
        assert count.fetchone()[0] == 0


def test_leave_with_balance_is_409(world):
    group = _create(world.c["Ana"])
    _join(world.db, group, world.ids["Bia"])
    _group_purchase(world, group, "Ana", 1000, {"Ana": 1, "Bia": 1})
    response = world.c["Bia"].delete(f"/api/groups/{group}/members/me")
    assert response.status_code == 409
    assert world.c["Bia"].get(f"/api/groups/{group}").status_code == 200


def test_leave_with_zero_balance_is_204(world):
    group = _create(world.c["Ana"])
    _join(world.db, group, world.ids["Bia"])
    _group_purchase(world, group, "Ana", 1000, {"Ana": 1, "Bia": 1})
    with psycopg.connect(world.db) as conn:
        conn.execute(
            "insert into settlement (group_id, from_person_id, to_person_id, amount_cents,"
            " paid_on, created_by_person_id) values (%s, %s, %s, 500, '2026-03-06', %s)",
            (group, world.ids["Bia"], world.ids["Ana"], world.ids["Bia"]),
        )
    assert world.c["Bia"].delete(f"/api/groups/{group}/members/me").status_code == 204
    assert world.c["Bia"].get(f"/api/groups/{group}").status_code == 404
    assert world.c["Bia"].get("/api/groups").json() == []


def test_owner_cannot_leave_with_others_inside(world):
    group = _create(world.c["Ana"])
    _join(world.db, group, world.ids["Bia"])
    assert world.c["Ana"].delete(f"/api/groups/{group}/members/me").status_code == 409
