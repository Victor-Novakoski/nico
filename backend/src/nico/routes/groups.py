"""Grupos: criar, ver membros, renomear, cadastrar membro sem login e sair (decisão 013).

Quem não é membro recebe 404 (não revela que o grupo existe); membro sem permissão recebe 403.
Do outro membro só aparecem id, nome e papel.
"""

from typing import Annotated
from uuid import UUID

import psycopg
from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel, ConfigDict, StringConstraints

from nico import groups, scope
from nico.auth import CurrentUser, current_user
from nico.db import get_conn
from nico.routes.people import PersonOut, add_person

router = APIRouter(prefix="/api/groups")

Conn = Annotated[psycopg.Connection, Depends(get_conn)]
User = Annotated[CurrentUser, Depends(current_user)]
Name = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=80)]


class GroupIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: Name


class MemberPersonIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: Name


class MemberOut(BaseModel):
    id: UUID
    name: str
    role: str


class GroupOut(BaseModel):
    id: UUID
    name: str
    role: str


class GroupDetailOut(GroupOut):
    members: list[MemberOut]


def _not_found() -> HTTPException:
    return HTTPException(status_code=404, detail="Grupo não encontrado")


def _my_role(conn: psycopg.Connection, group_id: UUID, me: str) -> str:
    row = conn.execute(
        "select role from group_member where group_id = %s and person_id = %s", (group_id, me)
    ).fetchone()
    if row is None:
        raise _not_found()
    return row[0]


def _detail(conn: psycopg.Connection, group_id: UUID, role: str) -> GroupDetailOut:
    name = conn.execute("select name from expense_group where id = %s", (group_id,)).fetchone()[0]
    rows = conn.execute(
        "select p.id, p.name, gm.role from group_member gm join person p on p.id = gm.person_id"
        " where gm.group_id = %s order by lower(p.name), p.name, p.id",
        (group_id,),
    ).fetchall()
    members = [MemberOut(id=r[0], name=r[1], role=r[2]) for r in rows]
    return GroupDetailOut(id=group_id, name=name, role=role, members=members)


def _balance(conn: psycopg.Connection, group_id: UUID, person_id: str) -> int:
    """Saldo da pessoa no grupo em centavos (compras do grupo e acertos)."""
    expenses: dict[UUID, groups.GroupExpense] = {}
    rows = conn.execute(
        "select p.id, pm.owner_person_id, p.total_cents, s.person_id, s.weight"
        " from purchase p join payment_method pm on pm.id = p.payment_method_id"
        " join purchase_share s on s.purchase_id = p.id where p.group_id = %s",
        (group_id,),
    ).fetchall()
    for purchase_id, payer, total, person, weight in rows:
        item = expenses.setdefault(purchase_id, groups.GroupExpense(str(payer), total, {}))
        item.shares[str(person)] = weight
    settlements = [
        groups.Settlement(str(r[0]), str(r[1]), r[2])
        for r in conn.execute(
            "select from_person_id, to_person_id, amount_cents from settlement where group_id = %s",
            (group_id,),
        )
    ]
    return groups.balances(expenses.values(), settlements).get(person_id, 0)


@router.post("", status_code=201)
def create_group(body: GroupIn, conn: Conn, user: User) -> GroupDetailOut:
    group_id = conn.execute(
        "insert into expense_group (name, created_by_person_id) values (%s, %s) returning id",
        (body.name, user.person_id),
    ).fetchone()[0]
    conn.execute(
        "insert into group_member (group_id, person_id, role) values (%s, %s, 'dono')",
        (group_id, user.person_id),
    )
    return _detail(conn, group_id, "dono")


@router.get("")
def list_groups(conn: Conn, user: User) -> list[GroupOut]:
    rows = conn.execute(
        "select g.id, g.name, gm.role from group_member gm"
        " join expense_group g on g.id = gm.group_id where gm.person_id = %s"
        " order by lower(g.name), g.name, g.id",
        (user.person_id,),
    ).fetchall()
    return [GroupOut(id=r[0], name=r[1], role=r[2]) for r in rows]


@router.get("/{group_id}")
def get_group(group_id: UUID, conn: Conn, user: User) -> GroupDetailOut:
    return _detail(conn, group_id, _my_role(conn, group_id, user.person_id))


@router.patch("/{group_id}")
def rename_group(group_id: UUID, body: GroupIn, conn: Conn, user: User) -> GroupDetailOut:
    role = _my_role(conn, group_id, user.person_id)
    if role != "dono":
        raise HTTPException(status_code=403, detail="Só o dono do grupo pode renomear")
    conn.execute("update expense_group set name = %s where id = %s", (body.name, group_id))
    return _detail(conn, group_id, role)


@router.post("/{group_id}/people", status_code=201)
def add_member_person(group_id: UUID, body: MemberPersonIn, conn: Conn, user: User) -> PersonOut:
    _my_role(conn, group_id, user.person_id)
    person_id, name = add_person(conn, body.name, group_id)
    return PersonOut(id=person_id, name=name)


@router.delete("/{group_id}/members/me", status_code=204)
def leave_group(group_id: UUID, conn: Conn, user: User) -> Response:
    role = _my_role(conn, group_id, user.person_id)
    # Bloqueia o grupo para o saldo não mudar entre a conferência e a saída.
    conn.execute("select 1 from expense_group where id = %s for update", (group_id,))
    if _balance(conn, group_id, user.person_id) != 0:
        raise HTTPException(
            status_code=409, detail="Você ainda tem saldo neste grupo. Acerte antes de sair"
        )
    if role == "dono" and len(scope.group_members(conn, group_id)) > 1:
        raise HTTPException(
            status_code=409, detail="O dono não pode sair enquanto há outros membros no grupo"
        )
    conn.execute(
        "delete from group_member where group_id = %s and person_id = %s",
        (group_id, user.person_id),
    )
    return Response(status_code=204)
