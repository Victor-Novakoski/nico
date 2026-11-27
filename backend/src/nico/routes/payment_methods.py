"""Cadastro de meios de pagamento (decisão 010) e dos apelidos que a pessoa fala."""

from typing import Annotated, Literal
from uuid import UUID

import psycopg
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, StringConstraints, model_validator

from nico.aliases import normalize
from nico.auth import CurrentUser, current_user
from nico.db import get_conn

router = APIRouter(prefix="/api/payment-methods")

Conn = Annotated[psycopg.Connection, Depends(get_conn)]
User = Annotated[CurrentUser, Depends(current_user)]
Name = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=80)]
Day = Annotated[int, Field(ge=1, le=31)]
Kind = Literal["credito", "debito", "pix", "dinheiro"]

SELECT = """
    select pm.id, pm.name, pm.owner_person_id, pm.kind, pm.closing_day, pm.due_day,
           coalesce(
               array_agg(a.alias order by a.alias) filter (where a.alias is not null), '{}'
           )
    from payment_method pm
    left join payment_method_alias a on a.payment_method_id = pm.id
"""
GROUP = " group by pm.id"


class PaymentMethodIn(BaseModel):
    name: Name
    owner_id: UUID
    kind: Kind
    closing_day: Day | None = None
    due_day: Day | None = None

    @model_validator(mode="after")
    def _days_only_for_credit(self) -> "PaymentMethodIn":
        has_days = self.closing_day is not None or self.due_day is not None
        if self.kind == "credito":
            if self.closing_day is None or self.due_day is None:
                raise ValueError("Cartão de crédito precisa do dia de fechamento e do vencimento")
        elif has_days:
            raise ValueError("Só o crédito tem dia de fechamento e de vencimento")
        return self


class AliasIn(BaseModel):
    alias: str


class PaymentMethodOut(BaseModel):
    id: UUID
    name: str
    owner_id: UUID
    kind: Kind
    closing_day: int | None
    due_day: int | None
    aliases: list[str]


def _out(row: tuple) -> PaymentMethodOut:
    return PaymentMethodOut(
        id=row[0],
        name=row[1],
        owner_id=row[2],
        kind=row[3],
        closing_day=row[4],
        due_day=row[5],
        aliases=list(row[6]),
    )


def _fetch(conn: psycopg.Connection, method_id: UUID, me: str) -> PaymentMethodOut | None:
    """Só devolve o meio se for da pessoa `me` (meio de outra pessoa é como se não existisse)."""
    row = conn.execute(
        SELECT + " where pm.id = %s and pm.owner_person_id = %s" + GROUP, (method_id, me)
    ).fetchone()
    return _out(row) if row else None


@router.post("", status_code=201)
def create_payment_method(body: PaymentMethodIn, conn: Conn, user: User) -> PaymentMethodOut:
    if str(body.owner_id) != user.person_id:
        raise HTTPException(status_code=422, detail="Só é possível cadastrar meio próprio")
    method_id = conn.execute(
        "insert into payment_method (owner_person_id, name, kind, closing_day, due_day)"
        " values (%s, %s, %s, %s, %s) returning id",
        (body.owner_id, body.name, body.kind, body.closing_day, body.due_day),
    ).fetchone()[0]
    return _fetch(conn, method_id, user.person_id)


@router.get("")
def list_payment_methods(conn: Conn, user: User) -> list[PaymentMethodOut]:
    rows = conn.execute(
        SELECT
        + " where pm.owner_person_id = %s"
        + GROUP
        + " order by lower(pm.name), pm.name, pm.id",
        (user.person_id,),
    ).fetchall()
    return [_out(r) for r in rows]


@router.post("/{method_id}/aliases", status_code=201)
def add_alias(method_id: UUID, body: AliasIn, conn: Conn, user: User) -> PaymentMethodOut:
    # Meio de outra pessoa: 404, antes de qualquer outra validação (não revela que existe).
    if _fetch(conn, method_id, user.person_id) is None:
        raise HTTPException(status_code=404, detail="Meio de pagamento não encontrado")
    alias = normalize(body.alias)
    if not alias:
        raise HTTPException(status_code=422, detail="Apelido vazio")
    try:
        conn.execute(
            "insert into payment_method_alias (payment_method_id, alias) values (%s, %s)",
            (method_id, alias),
        )
    except psycopg.errors.UniqueViolation:
        # TODO: índice único de apelido é global; deveria ser por dono (o 409 vaza apelido alheio).
        raise HTTPException(
            status_code=409, detail="Apelido já usado em outro meio de pagamento"
        ) from None
    return _fetch(conn, method_id, user.person_id)
