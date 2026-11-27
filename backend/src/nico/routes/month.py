"""Gastos à vista (débito, Pix e dinheiro) de um mês, com total por pessoa (decisão 010)."""

from datetime import date
from typing import Annotated
from uuid import UUID

import psycopg
from fastapi import APIRouter, Depends, Path
from pydantic import BaseModel

from nico import billing, scope
from nico.auth import CurrentUser, current_user
from nico.db import get_conn

router = APIRouter(prefix="/api/months")

Conn = Annotated[psycopg.Connection, Depends(get_conn)]
User = Annotated[CurrentUser, Depends(current_user)]


class CashItem(BaseModel):
    purchase_id: UUID
    description: str
    purchase_date: date
    amount_cents: int
    status: str
    payment_method_id: UUID
    shares: dict[str, int]


class CashOut(BaseModel):
    year: int
    month: int
    total_cents: int
    per_person: dict[str, int]
    pending_count: int
    items: list[CashItem]


@router.get("/{year}/{month}/cash")
def cash_month(
    year: Annotated[int, Path(ge=2000, le=2100)],
    month: Annotated[int, Path(ge=1, le=12)],
    conn: Conn,
    user: User,
) -> CashOut:
    start = date(year, month, 1)
    end = date(year + 1, 1, 1) if month == 12 else date(year, month + 1, 1)
    rows = conn.execute(
        "select p.id, p.description, p.purchase_date, p.total_cents, p.status, p.payment_method_id"
        " from purchase p join payment_method m on m.id = p.payment_method_id"
        " where m.kind <> 'credito' and p.purchase_date >= %(start)s"
        f" and p.purchase_date < %(end)s and {scope.READABLE_PURCHASE}"
        " order by p.purchase_date, p.description, p.id",
        {"start": start, "end": end, "me": user.person_id},
    ).fetchall()
    shares: dict[UUID, dict[str, int]] = {}
    for purchase_id, person_id, weight in conn.execute(
        "select purchase_id, person_id, weight from purchase_share where purchase_id = any(%s)",
        ([r[0] for r in rows],),
    ):
        shares.setdefault(purchase_id, {})[str(person_id)] = weight
    items = [
        CashItem(
            purchase_id=r[0],
            description=r[1],
            purchase_date=r[2],
            amount_cents=r[3],
            status=r[4],
            payment_method_id=r[5],
            shares=shares[r[0]],
        )
        for r in rows
    ]
    return CashOut(
        year=year,
        month=month,
        total_cents=sum(i.amount_cents for i in items),
        per_person=billing.person_totals((i.amount_cents, i.shares) for i in items),
        pending_count=sum(1 for i in items if i.status == "pendente"),
        items=items,
    )
