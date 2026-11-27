"""Isolamento entre pessoas e grupos nas rotas atuais (decisão 013). Dados inventados.

Ana e Caio estão no grupo A; Bia e Duda, no B. Quem não tem grupo em comum nunca vê nem mexe
no que é da outra pessoa: sempre 404 (422 onde a regra manda), e o dado fica intacto no banco.
"""

import uuid
from types import SimpleNamespace

import psycopg
import pytest
from fastapi.testclient import TestClient

from nico.auth import hash_password

PASSWORD = "senha-inventada-9"
DAY = "2026-03-05"


def _make_person(db_url, name: str) -> str:
    with psycopg.connect(db_url) as conn:
        person_id = conn.execute(
            "insert into person (name) values (%s) returning id", (name,)
        ).fetchone()[0]
        conn.execute(
            "insert into app_user (person_id, username, password_hash) values (%s, %s, %s)",
            (person_id, name.lower(), hash_password(PASSWORD)),
        )
    return str(person_id)


def _make_group(db_url, name: str, members: dict[str, str], **member_fields) -> str:
    """`members` é {person_id: papel}; `member_fields` vale para todos (ex.: show_expenses)."""
    with psycopg.connect(db_url) as conn:
        owner = next(p for p, r in members.items() if r == "dono")
        group_id = conn.execute(
            "insert into expense_group (name, created_by_person_id) values (%s, %s) returning id",
            (name, owner),
        ).fetchone()[0]
        for person_id, role in members.items():
            conn.execute(
                "insert into group_member (group_id, person_id, role) values (%s, %s, %s)",
                (group_id, person_id, role),
            )
    return str(group_id)


def _login(app, name: str) -> TestClient:
    # Sem `with`: o pool do app já foi aberto pelo fixture `client`.
    c = TestClient(app, base_url="https://testserver")
    response = c.post("/api/login", json={"username": name.lower(), "password": PASSWORD})
    assert response.status_code == 200
    return c


def _method(client, name="Cartão", kind="credito") -> str:
    owner = client.get("/api/me").json()["person_id"]
    body = {"name": name, "owner_id": owner, "kind": kind}
    if kind == "credito":
        body.update(closing_day=10, due_day=17)
    response = client.post("/api/payment-methods", json=body)
    assert response.status_code == 201
    return response.json()["id"]


def _buy(client, method_id, **fields) -> dict:
    body = {
        "id": str(uuid.uuid4()),
        "payment_method_id": method_id,
        "description": "Mercado",
        "total_cents": 9000,
        "purchase_date": DAY,
        "installments": 1,
    }
    body.update(fields)
    response = client.post("/api/purchases", json=body)
    assert response.status_code == 201, response.text
    return response.json()


@pytest.fixture
def world(client, db_url):
    """Ana e Caio no grupo A; Bia e Duda no B; cada uma com um cartão e um Pix."""
    from nico.app import app

    ids = {n: _make_person(db_url, n) for n in ("Ana", "Bia", "Caio", "Duda")}
    group_a = _make_group(db_url, "A", {ids["Ana"]: "dono", ids["Caio"]: "membro"})
    group_b = _make_group(db_url, "B", {ids["Bia"]: "dono", ids["Duda"]: "membro"})
    c = {n: _login(app, n) for n in ids}
    card = {n: _method(c[n], name=f"Cartão {n}") for n in ids}
    pix = {n: _method(c[n], name=f"Pix {n}", kind="pix") for n in ids}
    return SimpleNamespace(
        db=db_url, ids=ids, c=c, card=card, pix=pix, group_a=group_a, group_b=group_b
    )


def _row(db_url, sql: str, *params):
    with psycopg.connect(db_url) as conn:
        return conn.execute(sql, params).fetchone()


def _assert_purchase_intact(w, purchase: dict) -> None:
    row = _row(
        w.db,
        "select description, total_cents, status, group_id from purchase where id = %s",
        purchase["id"],
    )
    assert row is not None
    assert row[:3] == (purchase["description"], purchase["total_cents"], purchase["status"])


def _is_not_found(response) -> bool:
    return response.status_code == 404


# ---- meios de pagamento e apelidos ----


def test_methods_list_only_own(world):
    for name in ("Ana", "Bia"):
        listed = world.c[name].get("/api/payment-methods").json()
        assert {m["id"] for m in listed} == {world.card[name], world.pix[name]}


def test_cannot_create_method_for_someone_else(world):
    response = world.c["Bia"].post(
        "/api/payment-methods",
        json={"name": "Pix da Ana", "owner_id": world.ids["Ana"], "kind": "pix"},
    )
    assert response.status_code == 422
    assert "próprio" in response.json()["detail"]
    assert _row(world.db, "select count(*) from payment_method")[0] == 8


def test_alias_only_on_own_method(world):
    response = world.c["Bia"].post(
        f"/api/payment-methods/{world.card['Ana']}/aliases", json={"alias": "roxinho"}
    )
    assert response.status_code == 404
    assert response.json() == {"detail": "Meio de pagamento não encontrado"}
    missing = world.c["Bia"].post(
        f"/api/payment-methods/{uuid.uuid4()}/aliases", json={"alias": "roxinho"}
    )
    assert missing.status_code == 404
    assert missing.json() == response.json()
    assert _row(world.db, "select count(*) from payment_method_alias")[0] == 0
    # Mesmo grupo não dá acesso ao meio do outro membro.
    assert (
        world.c["Caio"]
        .post(f"/api/payment-methods/{world.card['Ana']}/aliases", json={"alias": "x"})
        .status_code
        == 404
    )


# ---- faturas ----


@pytest.mark.parametrize("who", ["Bia", "Caio"])
@pytest.mark.parametrize("path", ["invoices/current", "invoices/2026/3"])
def test_invoice_only_for_owner(world, who, path):
    _buy(world.c["Ana"], world.card["Ana"], group_id=world.group_a)
    owner = world.c["Ana"].get(f"/api/payment-methods/{world.card['Ana']}/{path}")
    assert owner.status_code == 200
    denied = world.c[who].get(f"/api/payment-methods/{world.card['Ana']}/{path}")
    assert denied.status_code == 404
    missing = world.c[who].get(f"/api/payment-methods/{uuid.uuid4()}/{path}")
    assert denied.json() == missing.json()


def test_invoice_shows_all_purchases_of_the_owner(world):
    ana = world.c["Ana"]
    personal = _buy(ana, world.card["Ana"], description="Pessoal")
    shared = _buy(ana, world.card["Ana"], description="Do grupo", group_id=world.group_a)
    invoice = ana.get(f"/api/payment-methods/{world.card['Ana']}/invoices/2026/3").json()
    assert {i["purchase_id"] for i in invoice["items"]} == {personal["id"], shared["id"]}


# ---- compras ----


def test_get_purchases_hidden_from_other_people(world):
    mine = _buy(world.c["Ana"], world.card["Ana"])
    shared = _buy(world.c["Ana"], world.card["Ana"], group_id=world.group_a)
    bia = world.c["Bia"]
    assert bia.get("/api/purchases").json() == []
    for p in (mine, shared):
        denied = bia.get(f"/api/purchases/{p['id']}")
        assert denied.status_code == 404
        assert denied.json() == bia.get(f"/api/purchases/{uuid.uuid4()}").json()
    # Caio (mesmo grupo) lê a do grupo, mas não a pessoal (show_expenses = 'grupo').
    caio = world.c["Caio"]
    assert [p["id"] for p in caio.get("/api/purchases").json()] == [shared["id"]]
    assert caio.get(f"/api/purchases/{shared['id']}").json()["group_id"] == world.group_a
    assert caio.get(f"/api/purchases/{mine['id']}").status_code == 404


@pytest.mark.parametrize("who", ["Bia", "Caio"])
def test_cannot_edit_or_delete_what_is_not_yours(world, who):
    personal = _buy(world.c["Ana"], world.card["Ana"])
    client = world.c[who]
    for method, kwargs in (
        ("patch", {"json": {"description": "invadido"}}),
        ("patch", {"json": {"status": "conferido"}}),
        ("delete", {}),
    ):
        response = getattr(client, method)(f"/api/purchases/{personal['id']}", **kwargs)
        assert response.status_code == 404
        assert response.json() == {"detail": "Compra não encontrada"}
    _assert_purchase_intact(world, personal)


def test_group_member_reads_but_cannot_edit_without_launching_or_owning_method(world):
    shared = _buy(world.c["Ana"], world.card["Ana"], group_id=world.group_a)
    caio = world.c["Caio"]
    assert caio.get(f"/api/purchases/{shared['id']}").status_code == 200
    assert (
        caio.patch(f"/api/purchases/{shared['id']}", json={"description": "x"}).status_code == 404
    )
    assert caio.delete(f"/api/purchases/{shared['id']}").status_code == 404
    _assert_purchase_intact(world, shared)


def test_method_owner_edits_group_purchase_launched_by_other_member(world):
    """Caio lança no grupo com o meio dele; Ana, que não lançou nem é dona, não edita."""
    shared = _buy(world.c["Caio"], world.card["Caio"], group_id=world.group_a)
    assert (
        world.c["Ana"]
        .patch(f"/api/purchases/{shared['id']}", json={"description": "x"})
        .status_code
        == 404
    )
    assert (
        world.c["Caio"]
        .patch(f"/api/purchases/{shared['id']}", json={"description": "ok"})
        .status_code
        == 200
    )


def test_show_expenses_todos_gives_read_only(world):
    with psycopg.connect(world.db) as conn:
        conn.execute(
            "update group_member set show_expenses = 'todos' where person_id = %s",
            (world.ids["Ana"],),
        )
    personal = _buy(world.c["Ana"], world.card["Ana"])
    caio = world.c["Caio"]
    assert caio.get(f"/api/purchases/{personal['id']}").status_code == 200
    assert personal["id"] in [p["id"] for p in caio.get("/api/purchases").json()]
    assert (
        caio.patch(f"/api/purchases/{personal['id']}", json={"status": "conferido"}).status_code
        == 404
    )
    assert caio.delete(f"/api/purchases/{personal['id']}").status_code == 404
    _assert_purchase_intact(world, personal)
    # Quem não está no grupo continua sem ver.
    assert world.c["Bia"].get(f"/api/purchases/{personal['id']}").status_code == 404


def test_leaving_group_loses_access(world):
    shared = _buy(world.c["Ana"], world.card["Ana"], group_id=world.group_a)
    caio = world.c["Caio"]
    assert caio.get(f"/api/purchases/{shared['id']}").status_code == 200
    with psycopg.connect(world.db) as conn:
        conn.execute("delete from group_member where person_id = %s", (world.ids["Caio"],))
    assert caio.get(f"/api/purchases/{shared['id']}").status_code == 404
    assert caio.get("/api/purchases").json() == []
    assert world.c["Ana"].get(f"/api/purchases/{shared['id']}").status_code == 200


def test_leaving_group_loses_edit_even_if_launched_it(world):
    shared = _buy(world.c["Caio"], world.card["Caio"], group_id=world.group_a)
    with psycopg.connect(world.db) as conn:
        conn.execute("delete from group_member where person_id = %s", (world.ids["Caio"],))
    caio = world.c["Caio"]
    assert (
        caio.patch(f"/api/purchases/{shared['id']}", json={"description": "x"}).status_code == 404
    )
    assert caio.delete(f"/api/purchases/{shared['id']}").status_code == 404
    _assert_purchase_intact(world, shared)


def test_post_with_repeated_id_of_unreadable_purchase_is_404(world):
    mine = _buy(world.c["Ana"], world.card["Ana"])
    body = {
        "id": mine["id"],
        "payment_method_id": world.card["Bia"],
        "description": "Outra coisa",
        "total_cents": 1,
        "purchase_date": DAY,
    }
    response = world.c["Bia"].post("/api/purchases", json=body)
    assert response.status_code == 404
    assert "Mercado" not in response.text
    _assert_purchase_intact(world, mine)
    # A dona reenviando continua recebendo 200 com a própria compra.
    assert (
        world.c["Ana"]
        .post("/api/purchases", json={**body, "payment_method_id": world.card["Ana"]})
        .status_code
        == 200
    )


def test_cannot_post_with_someone_elses_method(world):
    body = {
        "id": str(uuid.uuid4()),
        "payment_method_id": world.card["Ana"],
        "description": "Roubo",
        "total_cents": 100,
        "purchase_date": DAY,
    }
    for who in ("Bia", "Caio"):
        response = world.c[who].post("/api/purchases", json=body)
        assert response.status_code == 422
        assert response.json()["detail"] == "Meio de pagamento não encontrado"
    assert _row(world.db, "select count(*) from purchase")[0] == 0


def test_cannot_post_in_group_you_are_not_in(world):
    body = {
        "id": str(uuid.uuid4()),
        "payment_method_id": world.card["Bia"],
        "group_id": world.group_a,
        "description": "Intruso",
        "total_cents": 100,
        "purchase_date": DAY,
    }
    assert world.c["Bia"].post("/api/purchases", json=body).status_code == 404
    assert (
        world.c["Bia"]
        .post("/api/purchases", json={**body, "group_id": str(uuid.uuid4())})
        .status_code
        == 404
    )
    assert _row(world.db, "select count(*) from purchase")[0] == 0


def test_shares_must_respect_scope(world):
    ana, ids = world.c["Ana"], world.ids
    base = {
        "payment_method_id": world.card["Ana"],
        "description": "Dividida",
        "total_cents": 1000,
        "purchase_date": DAY,
    }

    def share(*people):
        return [{"person_id": ids[p], "weight": 1} for p in people]

    def post(**fields):
        return ana.post("/api/purchases", json={"id": str(uuid.uuid4()), **base, **fields})

    # Pessoal: só eu.
    assert post(shares=share("Ana")).status_code == 201
    assert post(shares=share("Ana", "Caio")).status_code == 422
    assert post(shares=share("Bia")).status_code == 422
    # De grupo: só membros.
    assert post(group_id=world.group_a, shares=share("Ana", "Caio")).status_code == 201
    assert post(group_id=world.group_a, shares=share("Ana", "Bia")).status_code == 422
    # Pessoa que não existe tem o mesmo erro de quem existe fora do grupo.
    ghost = [{"person_id": str(uuid.uuid4()), "weight": 1}]
    assert post(group_id=world.group_a, shares=ghost).status_code == 422


def test_patch_shares_and_method_follow_scope(world):
    ana = world.c["Ana"]
    shared = _buy(ana, world.card["Ana"], group_id=world.group_a)
    url = f"/api/purchases/{shared['id']}"
    assert (
        ana.patch(url, json={"shares": [{"person_id": world.ids["Bia"], "weight": 1}]}).status_code
        == 422
    )
    assert (
        ana.patch(url, json={"shares": [{"person_id": world.ids["Caio"], "weight": 1}]}).status_code
        == 200
    )
    assert ana.patch(url, json={"payment_method_id": world.card["Bia"]}).status_code == 422
    assert ana.patch(url, json={"group_id": world.group_b}).status_code == 422
    personal = _buy(ana, world.card["Ana"])
    assert (
        ana.patch(
            f"/api/purchases/{personal['id']}",
            json={"shares": [{"person_id": world.ids["Caio"], "weight": 1}]},
        ).status_code
        == 422
    )
    row = _row(
        world.db, "select group_id, payment_method_id from purchase where id = %s", shared["id"]
    )
    assert (str(row[0]), str(row[1])) == (world.group_a, world.card["Ana"])


# ---- mês à vista ----


def test_cash_month_only_readable(world):
    mine = _buy(world.c["Ana"], world.pix["Ana"], description="Pão")
    shared = _buy(world.c["Ana"], world.pix["Ana"], description="Feira", group_id=world.group_a)
    other = _buy(world.c["Bia"], world.pix["Bia"], description="Segredo")

    def ids_of(name):
        data = world.c[name].get("/api/months/2026/3/cash").json()
        return {i["purchase_id"] for i in data["items"]}

    assert ids_of("Ana") == {mine["id"], shared["id"]}
    assert ids_of("Caio") == {shared["id"]}
    assert ids_of("Bia") == {other["id"]}
    assert ids_of("Duda") == set()


# ---- pessoas ----


def test_people_list_only_self_and_group_members(world):
    def names(who):
        return {p["name"] for p in world.c[who].get("/api/people").json()}

    assert names("Ana") == {"Ana", "Caio"}
    assert names("Caio") == {"Ana", "Caio"}
    assert names("Bia") == {"Bia", "Duda"}


def test_person_created_in_group_is_member_only_for_that_group(world):
    response = world.c["Ana"].post("/api/people", json={"name": "Edu", "group_id": world.group_a})
    assert response.status_code == 201
    assert "Edu" in {p["name"] for p in world.c["Caio"].get("/api/people").json()}
    assert "Edu" not in {p["name"] for p in world.c["Bia"].get("/api/people").json()}
    role = _row(
        world.db, "select role from group_member where person_id = %s", response.json()["id"]
    )
    assert role == ("membro",)


def test_cannot_add_person_to_group_you_are_not_in(world):
    before = _row(world.db, "select count(*) from person")[0]
    response = world.c["Bia"].post(
        "/api/people", json={"name": "Intruso", "group_id": world.group_a}
    )
    assert response.status_code == 404
    assert _row(world.db, "select count(*) from person")[0] == before


def test_person_without_group_is_invisible_to_others(world):
    assert world.c["Ana"].post("/api/people", json={"name": "Solta"}).status_code == 201
    assert "Solta" not in {p["name"] for p in world.c["Caio"].get("/api/people").json()}


# ---- settings ----


def test_default_method_must_be_own(world):
    bia = world.c["Bia"]
    assert (
        bia.patch("/api/me/settings", json={"default_method_id": world.card["Ana"]}).status_code
        == 422
    )
    ghost = bia.patch("/api/me/settings", json={"default_method_id": str(uuid.uuid4())})
    assert ghost.status_code == 422
    assert (
        ghost.json()
        == bia.patch("/api/me/settings", json={"default_method_id": world.card["Ana"]}).json()
    )
    assert bia.get("/api/me/settings").json()["default_method_id"] is None
    assert (
        bia.patch("/api/me/settings", json={"default_method_id": world.card["Bia"]}).status_code
        == 200
    )


def test_group_purchase_without_shares_splits_equally_among_members(world):
    bought = _buy(world.c["Ana"], world.card["Ana"], group_id=world.group_a)
    people = {s["person_id"]: s["weight"] for s in bought["shares"]}
    assert people == {world.ids["Ana"]: 1, world.ids["Caio"]: 1}


# Rascunhos (/api/drafts): só os meios da própria pessoa e as pessoas dos grupos dela.


def _parse(client, text: str) -> dict:
    response = client.post("/api/drafts/parse", json={"text": text})
    assert response.status_code == 200, response.text
    return response.json()


def test_drafts_ignore_alias_of_someone_elses_method(world):
    alias = world.c["Ana"].post(
        f"/api/payment-methods/{world.card['Ana']}/aliases", json={"alias": "lilas"}
    )
    assert alias.status_code == 201, alias.text
    own = _parse(world.c["Ana"], "50 mercado no lilas")
    assert own["drafts"][0]["method_id"] == world.card["Ana"]
    for who in ("Bia", "Caio"):  # de outro grupo e do mesmo grupo
        result = _parse(world.c[who], "50 mercado no lilas")
        assert all(d["method_id"] != world.card["Ana"] for d in result["drafts"])
        # Nem o nome do meio alheio vale como apelido.
        result = _parse(world.c[who], "50 mercado no cartão ana")
        assert all(d["method_id"] != world.card["Ana"] for d in result["drafts"])


def test_ai_gets_only_own_methods_and_visible_people(world):
    from nico.ai.cascade import Cascade
    from nico.ai.schema import Extraction
    from nico.app import app
    from nico.routes.drafts import get_cascade

    seen = []

    class Spy:
        def extract(self, text, context):
            seen.append(context)
            return Extraction(items=[])

    client = world.c["Ana"]
    assert client.patch("/api/me/settings", json={"ai_enabled": True}).status_code == 200
    app.dependency_overrides[get_cascade] = lambda: Cascade([("spy", Spy())])
    try:
        _parse(client, "paguei o mercado ontem no roxo")
    finally:
        app.dependency_overrides.pop(get_cascade, None)
    [context] = seen
    assert {m.id for m in context.methods} == {world.card["Ana"], world.pix["Ana"]}
    assert {p.id for p in context.people} == {world.ids["Ana"], world.ids["Caio"]}
