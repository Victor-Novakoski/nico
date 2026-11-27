"""Escopo e isolamento: o que cada pessoa pode ler e alterar (decisão 013).

Todo SQL aqui usa parâmetros; nunca monte consulta com dado da pessoa. Quem usa estas funções
responde 404 (nunca 403) quando a negação vem daqui, para não revelar que o dado existe.
"""

from uuid import UUID

import psycopg

# Fragmento para `where`: compras (alias `p`) que a pessoa `%(me)s` pode LER. Só aceita parâmetros
# nomeados. Quatro caminhos: compra de um grupo dela; compra pessoal dela; compra pessoal de quem
# escolheu `show_expenses = 'todos'` em um grupo em comum (só leitura); compra num meio de
# pagamento dela (a fatura mostra tudo do dono).
READABLE_PURCHASE = """(
    p.group_id in (select gm.group_id from group_member gm where gm.person_id = %(me)s)
    or (p.group_id is null and p.created_by_person_id = %(me)s)
    or (p.group_id is null and exists (
        select 1 from group_member mine
        join group_member theirs on theirs.group_id = mine.group_id
        where mine.person_id = %(me)s
          and theirs.person_id = p.created_by_person_id
          and theirs.show_expenses = 'todos'
    ))
    or exists (
        select 1 from payment_method pm
        where pm.id = p.payment_method_id and pm.owner_person_id = %(me)s
    )
)"""


def group_ids(conn: psycopg.Connection, person_id: UUID | str) -> set[UUID]:
    """Grupos em que a pessoa está."""
    rows = conn.execute("select group_id from group_member where person_id = %s", (person_id,))
    return {r[0] for r in rows}


def is_member(conn: psycopg.Connection, person_id: UUID | str, group_id: UUID) -> bool:
    return (
        conn.execute(
            "select 1 from group_member where group_id = %s and person_id = %s",
            (group_id, person_id),
        ).fetchone()
        is not None
    )


def group_members(conn: psycopg.Connection, group_id: UUID) -> set[UUID]:
    rows = conn.execute("select person_id from group_member where group_id = %s", (group_id,))
    return {r[0] for r in rows}


def visible_people(conn: psycopg.Connection, person_id: UUID | str) -> set[UUID]:
    """A própria pessoa e os membros dos grupos dela."""
    rows = conn.execute(
        "select %(me)s::uuid union"
        " select other.person_id from group_member mine"
        " join group_member other on other.group_id = mine.group_id"
        " where mine.person_id = %(me)s",
        {"me": person_id},
    )
    return {r[0] for r in rows}


def can_read_purchase(conn: psycopg.Connection, person_id: UUID | str, purchase_id: UUID) -> bool:
    row = conn.execute(
        f"select 1 from purchase p where p.id = %(id)s and {READABLE_PURCHASE}",  # noqa: S608
        {"id": purchase_id, "me": person_id},
    ).fetchone()
    return row is not None


def can_edit_purchase(conn: psycopg.Connection, person_id: UUID | str, purchase_id: UUID) -> bool:
    """Pessoal: só quem lançou. De grupo: quem lançou ou o dono do meio, se ainda é membro."""
    row = conn.execute(
        "select p.group_id, p.created_by_person_id, pm.owner_person_id"
        " from purchase p join payment_method pm on pm.id = p.payment_method_id"
        " where p.id = %s",
        (purchase_id,),
    ).fetchone()
    if row is None:
        return False
    group_id, created_by, method_owner = row
    me = UUID(str(person_id))
    if group_id is None:
        return created_by == me
    return me in (created_by, method_owner) and is_member(conn, me, group_id)


def owns_method(conn: psycopg.Connection, person_id: UUID | str, method_id: UUID) -> bool:
    return (
        conn.execute(
            "select 1 from payment_method where id = %s and owner_person_id = %s",
            (method_id, person_id),
        ).fetchone()
        is not None
    )
