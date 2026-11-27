import uuid

import psycopg

URL = "/api/purchases"


def person_id(client) -> str:
    return client.get("/api/me").json()["person_id"]


def make_method(client, **fields) -> str:
    body = {"name": "Cartão Azul", "owner_id": person_id(client), "kind": "credito"}
    if fields.get("kind", "credito") == "credito":
        body.update(closing_day=10, due_day=17)
    body.update(fields)
    response = client.post("/api/payment-methods", json=body)
    assert response.status_code == 201
    return response.json()["id"]


def make_group(db_url, client) -> str:
    """Grupo com a Fulana como dona; devolve o id."""
    with psycopg.connect(db_url) as conn:
        group_id = conn.execute(
            "insert into expense_group (name, created_by_person_id) values ('Casa', %s)"
            " returning id",
            (person_id(client),),
        ).fetchone()[0]
        conn.execute(
            "insert into group_member (group_id, person_id, role) values (%s, %s, 'dono')",
            (group_id, person_id(client)),
        )
    return str(group_id)


def make_person(client, group_id, name="Beltrano") -> str:
    response = client.post("/api/people", json={"name": name, "group_id": group_id})
    return response.json()["id"]


def body(method_id, **fields) -> dict:
    data = {
        "id": str(uuid.uuid4()),
        "payment_method_id": method_id,
        "description": "Mercado",
        "total_cents": 30000,
        "purchase_date": "2026-03-05",
        "installments": 3,
    }
    data.update(fields)
    return data


def post(client, method_id, **fields):
    return client.post(URL, json=body(method_id, **fields))


def test_requires_login(client):
    some = str(uuid.uuid4())
    assert client.get(URL).status_code == 401
    assert client.post(URL, json={}).status_code == 401
    assert client.get(f"{URL}/{some}").status_code == 401
    assert client.patch(f"{URL}/{some}", json={"status": "conferido"}).status_code == 401
    assert client.delete(f"{URL}/{some}").status_code == 401


def test_create_credit_in_3_installments(logged_client):
    client = logged_client
    method = make_method(client)
    response = post(client, method)
    assert response.status_code == 201
    purchase = response.json()
    assert purchase["status"] == "pendente"
    assert purchase["created_by_person_id"] == person_id(client)
    assert purchase["shares"] == [{"person_id": person_id(client), "weight": 1}]
    installments = purchase["installments_list"]
    assert [i["number"] for i in installments] == [1, 2, 3]
    assert [i["amount_cents"] for i in installments] == [10000, 10000, 10000]
    assert [(i["invoice"]["year"], i["invoice"]["month"]) for i in installments] == [
        (2026, 3),
        (2026, 4),
        (2026, 5),
    ]
    assert installments[0]["invoice"]["closing_date"] == "2026-03-10"
    assert installments[0]["invoice"]["due_date"] == "2026-03-17"
    assert client.get(f"{URL}/{purchase['id']}").json() == purchase


def test_created_by_comes_only_from_logged_user(logged_client):
    client = logged_client
    method = make_method(client)
    response = post(client, method, created_by_person_id=str(uuid.uuid4()))
    assert response.status_code == 422


def test_resend_same_id_does_not_duplicate(logged_client):
    client = logged_client
    method = make_method(client)
    data = body(method)
    first = client.post(URL, json=data)
    again = client.post(URL, json=data)
    assert first.status_code == 201
    assert again.status_code == 200
    assert again.json() == first.json()
    assert len(client.get(URL).json()) == 1


def test_cash_with_installments_is_422(logged_client):
    client = logged_client
    pix = make_method(client, name="Pix", kind="pix")
    assert post(client, pix, installments=3).status_code == 422
    ok = post(client, pix, installments=1)
    assert ok.status_code == 201
    assert ok.json()["installments_list"] == []


def test_invalid_input_is_422(logged_client):
    client = logged_client
    method = make_method(client)
    assert post(client, method, total_cents=100.5).status_code == 422
    assert post(client, method, total_cents=True).status_code == 422
    assert post(client, method, total_cents=-1).status_code == 422
    assert post(client, method, installments=0).status_code == 422
    assert post(client, method, description="   ").status_code == 422
    assert post(client, method, status="outro").status_code == 422
    assert post(client, str(uuid.uuid4())).status_code == 422
    stranger = {"person_id": str(uuid.uuid4()), "weight": 1}
    assert post(client, method, shares=[stranger]).status_code == 422
    assert client.get(URL).json() == []


def test_create_with_shares(logged_client, auth_env):
    client = logged_client
    method = make_method(client)
    group = make_group(auth_env, client)
    other = make_person(client, group)
    shares = [{"person_id": person_id(client), "weight": 1}, {"person_id": other, "weight": 2}]
    assert post(client, method, shares=shares).status_code == 422  # dividida sem grupo
    purchase = post(client, method, shares=shares, group_id=group).json()
    assert {s["person_id"]: s["weight"] for s in purchase["shares"]} == {
        person_id(client): 1,
        other: 2,
    }
    dup = [{"person_id": other, "weight": 1}, {"person_id": other, "weight": 2}]
    assert post(client, method, shares=dup, group_id=group).status_code == 422


def test_list_with_status_filter(logged_client):
    client = logged_client
    method = make_method(client)
    old = post(client, method, installments=1, purchase_date="2026-03-01").json()
    new = post(client, method, installments=1, purchase_date="2026-03-09").json()
    done = post(client, method, installments=1, status="conferido").json()
    ids = [p["id"] for p in client.get(URL).json()]
    assert ids.index(new["id"]) < ids.index(old["id"])
    pending = client.get(URL, params={"status": "pendente"}).json()
    assert {p["id"] for p in pending} == {old["id"], new["id"]}
    checked = client.get(URL, params={"status": "conferido"}).json()
    assert [p["id"] for p in checked] == [done["id"]]
    assert client.get(URL, params={"status": "x"}).status_code == 422


def test_get_missing_is_404(logged_client):
    assert logged_client.get(f"{URL}/{uuid.uuid4()}").status_code == 404


def test_patch_status_to_checked(logged_client):
    client = logged_client
    purchase = post(client, make_method(client)).json()
    response = client.patch(f"{URL}/{purchase['id']}", json={"status": "conferido"})
    assert response.status_code == 200
    assert response.json() == {**purchase, "status": "conferido"}


def test_patch_installments_rebuilds(logged_client):
    client = logged_client
    purchase = post(client, make_method(client)).json()
    response = client.patch(f"{URL}/{purchase['id']}", json={"installments": 2})
    assert response.status_code == 200
    updated = response.json()
    assert updated["installments"] == 2
    assert [i["amount_cents"] for i in updated["installments_list"]] == [15000, 15000]
    assert [i["invoice"]["month"] for i in updated["installments_list"]] == [3, 4]
    assert updated["installments_list"][0]["invoice"] == purchase["installments_list"][0]["invoice"]


def test_patch_total_and_description(logged_client):
    client = logged_client
    purchase = post(client, make_method(client)).json()
    response = client.patch(
        f"{URL}/{purchase['id']}", json={"total_cents": 9000, "description": "  Feira  "}
    )
    updated = response.json()
    assert updated["description"] == "Feira"
    assert [i["amount_cents"] for i in updated["installments_list"]] == [3000, 3000, 3000]


def test_patch_credit_to_pix_removes_installments(logged_client):
    client = logged_client
    pix = make_method(client, name="Pix", kind="pix")
    purchase = post(client, make_method(client), installments=1).json()
    assert len(purchase["installments_list"]) == 1
    response = client.patch(f"{URL}/{purchase['id']}", json={"payment_method_id": pix})
    assert response.status_code == 200
    assert response.json()["payment_method_id"] == pix
    assert response.json()["installments_list"] == []


def test_patch_shares(logged_client, auth_env):
    client = logged_client
    group = make_group(auth_env, client)
    purchase = post(client, make_method(client), group_id=group).json()
    other = make_person(client, group)
    response = client.patch(
        f"{URL}/{purchase['id']}", json={"shares": [{"person_id": other, "weight": 3}]}
    )
    assert response.json()["shares"] == [{"person_id": other, "weight": 3}]
    reset = client.patch(f"{URL}/{purchase['id']}", json={"shares": []})
    assert reset.json()["shares"] == [{"person_id": person_id(client), "weight": 1}]
    stranger = [{"person_id": str(uuid.uuid4()), "weight": 1}]
    assert client.patch(f"{URL}/{purchase['id']}", json={"shares": stranger}).status_code == 422


def test_patch_cash_with_installments_is_422(logged_client):
    client = logged_client
    pix = make_method(client, name="Pix", kind="pix")
    purchase = post(client, pix, installments=1).json()
    response = client.patch(f"{URL}/{purchase['id']}", json={"installments": 2})
    assert response.status_code == 422
    assert client.get(f"{URL}/{purchase['id']}").json() == purchase


def test_patch_invalid_and_missing(logged_client):
    client = logged_client
    purchase = post(client, make_method(client)).json()
    url = f"{URL}/{purchase['id']}"
    assert client.patch(url, json={}).status_code == 422
    assert client.patch(url, json={"description": None}).status_code == 422
    assert client.patch(url, json={"total_cents": 1.5}).status_code == 422
    assert client.patch(url, json={"created_by_person_id": str(uuid.uuid4())}).status_code == 422
    assert client.patch(url, json={"payment_method_id": str(uuid.uuid4())}).status_code == 422
    assert client.patch(f"{URL}/{uuid.uuid4()}", json={"status": "conferido"}).status_code == 404


def test_delete(logged_client):
    client = logged_client
    purchase = post(client, make_method(client)).json()
    assert client.delete(f"{URL}/{purchase['id']}").status_code == 204
    assert client.get(f"{URL}/{purchase['id']}").status_code == 404
    assert client.delete(f"{URL}/{purchase['id']}").status_code == 404
