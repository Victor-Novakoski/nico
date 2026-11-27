import psycopg
import pytest

# `logged_client` (conftest) já cria e loga a usuária Fulana, que é uma pessoa da casa.


def make_group(db_url, client) -> str:
    """Grupo com a Fulana como dona; devolve o id."""
    me = client.get("/api/me").json()["person_id"]
    with psycopg.connect(db_url) as conn:
        group_id = conn.execute(
            "insert into expense_group (name, created_by_person_id) values ('Casa', %s)"
            " returning id",
            (me,),
        ).fetchone()[0]
        conn.execute(
            "insert into group_member (group_id, person_id, role) values (%s, %s, 'dono')",
            (group_id, me),
        )
    return str(group_id)


def names(client) -> list[str]:
    return [p["name"] for p in client.get("/api/people").json()]


def test_requires_login(client):
    assert client.get("/api/people").status_code == 401
    assert client.post("/api/people", json={"name": "Ciclano"}).status_code == 401


def test_list_starts_with_logged_person(logged_client):
    client = logged_client
    response = client.get("/api/people")
    assert response.status_code == 200
    assert names(client) == ["Fulana"]


def test_create_and_list(logged_client, auth_env):
    client = logged_client
    group = make_group(auth_env, client)
    response = client.post("/api/people", json={"name": "Beltrano", "group_id": group})
    assert response.status_code == 201
    created = response.json()
    assert created["name"] == "Beltrano"
    assert created["id"]
    assert created in client.get("/api/people").json()


def test_list_is_sorted_by_name_ignoring_case(logged_client, auth_env):
    client = logged_client
    group = make_group(auth_env, client)
    for name in ["beltrano", "Ciclano", "ana"]:
        client.post("/api/people", json={"name": name, "group_id": group})
    assert names(client) == ["ana", "beltrano", "Ciclano", "Fulana"]


@pytest.mark.parametrize("name", ["", "   ", "x" * 81])
def test_invalid_name_is_422(logged_client, name):
    client = logged_client
    assert client.post("/api/people", json={"name": name}).status_code == 422
    assert names(client) == ["Fulana"]


def test_name_is_trimmed(logged_client):
    client = logged_client
    response = client.post("/api/people", json={"name": "  Beltrano  "})
    assert response.status_code == 201
    assert response.json()["name"] == "Beltrano"


def test_max_length_name_is_accepted(logged_client):
    client = logged_client
    assert client.post("/api/people", json={"name": "x" * 80}).status_code == 201
