"""Cadastro de pessoas da casa."""

from typing import Annotated
from uuid import UUID

import psycopg
from fastapi import APIRouter, Depends
from pydantic import BaseModel, StringConstraints

from nico.db import get_conn

router = APIRouter(prefix="/api/people")

Conn = Annotated[psycopg.Connection, Depends(get_conn)]
Name = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=80)]


class PersonIn(BaseModel):
    name: Name


class PersonOut(BaseModel):
    id: UUID
    name: str


@router.post("", status_code=201)
def create_person(body: PersonIn, conn: Conn) -> PersonOut:
    row = conn.execute(
        "insert into person (name) values (%s) returning id, name", (body.name,)
    ).fetchone()
    return PersonOut(id=row[0], name=row[1])


@router.get("")
def list_people(conn: Conn) -> list[PersonOut]:
    rows = conn.execute("select id, name from person order by lower(name), name, id").fetchall()
    return [PersonOut(id=r[0], name=r[1]) for r in rows]
