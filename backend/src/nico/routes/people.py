"""Cadastro de pessoas: cada uma vê só ela mesma e os membros dos grupos dela (decisão 013)."""

from typing import Annotated
from uuid import UUID

import psycopg
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, StringConstraints

from nico import scope
from nico.auth import CurrentUser, current_user
from nico.db import get_conn

router = APIRouter(prefix="/api/people")

Conn = Annotated[psycopg.Connection, Depends(get_conn)]
User = Annotated[CurrentUser, Depends(current_user)]
Name = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=80)]


class PersonIn(BaseModel):
    name: Name
    group_id: UUID | None = None


class PersonOut(BaseModel):
    id: UUID
    name: str


@router.post("", status_code=201)
def create_person(body: PersonIn, conn: Conn, user: User) -> PersonOut:
    """Com `group_id`, a pessoa nova entra no grupo como membro; sem ele, fica sem grupo."""
    if body.group_id is not None and not scope.is_member(conn, user.person_id, body.group_id):
        raise HTTPException(status_code=404, detail="Grupo não encontrado")
    row = conn.execute(
        "insert into person (name) values (%s) returning id, name", (body.name,)
    ).fetchone()
    if body.group_id is not None:
        conn.execute(
            "insert into group_member (group_id, person_id, role) values (%s, %s, 'membro')",
            (body.group_id, row[0]),
        )
    return PersonOut(id=row[0], name=row[1])


@router.get("")
def list_people(conn: Conn, user: User) -> list[PersonOut]:
    ids = list(scope.visible_people(conn, user.person_id))
    rows = conn.execute(
        "select id, name from person where id = any(%s) order by lower(name), name, id", (ids,)
    ).fetchall()
    return [PersonOut(id=r[0], name=r[1]) for r in rows]
