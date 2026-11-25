"""Fatura de um meio de crédito, com total por pessoa (decisões 004, 008 e 010)."""

from datetime import date
from typing import Annotated
from uuid import UUID

import psycopg
from fastapi import APIRouter, Depends, HTTPException, Path
from pydantic import BaseModel

from nico import billing, dates
from nico.db import get_conn

router = APIRouter(prefix="/api/payment-methods")

Conn = Annotated[psycopg.Connection, Depends(get_conn)]


class InvoiceItem(BaseModel):
    purchase_id: UUID
    description: str
    purchase_date: date
    installment_number: int
    installments: int
    amount_cents: int
    status: str
    shares: dict[str, int]


class InvoiceOut(BaseModel):
    payment_method_id: UUID
    year: int
    month: int
    closing_date: date
    due_date: date
    exists: bool
    total_cents: int
    per_person: dict[str, int]
    pending_count: int
    items: list[InvoiceItem]


def _card(conn: psycopg.Connection, method_id: UUID) -> billing.Card:
    row = conn.execute(
        "select kind, closing_day, due_day from payment_method where id = %s", (method_id,)
    ).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="Meio de pagamento não encontrado")
    if row[0] != "credito":
        raise HTTPException(status_code=422, detail="Só cartão de crédito tem fatura")
    return billing.Card(row[1], row[2])


def _computed(card: billing.Card, year: int, month: int) -> billing.Invoice:
    """Fatura da competência (mês do vencimento) quando ainda não há linha gravada."""
    if card.due_day > card.closing_day:
        closing_year, closing_month = year, month
    else:
        closing_year, closing_month = (year - 1, 12) if month == 1 else (year, month - 1)
    seed_date = date(closing_year, closing_month, 1)
    seed = billing.Invoice(closing_year, closing_month, seed_date, seed_date)
    return billing.next_invoice(card, seed, 0)


def _build(
    conn: psycopg.Connection, method_id: UUID, card: billing.Card, year: int, month: int
) -> InvoiceOut:
    row = conn.execute(
        "select id, closing_date, due_date from invoice"
        " where payment_method_id = %s and year = %s and month = %s",
        (method_id, year, month),
    ).fetchone()
    if row is None:
        computed = _computed(card, year, month)
        return InvoiceOut(
            payment_method_id=method_id,
            year=year,
            month=month,
            closing_date=computed.closing_date,
            due_date=computed.due_date,
            exists=False,
            total_cents=0,
            per_person={},
            pending_count=0,
            items=[],
        )
    invoice_id, closing_date, due_date = row
    rows = conn.execute(
        "select p.id, p.description, p.purchase_date, i.number, p.installments,"
        " i.amount_cents, p.status"
        " from installment i join purchase p on p.id = i.purchase_id"
        " where i.invoice_id = %s order by p.purchase_date, p.description, p.id, i.number",
        (invoice_id,),
    ).fetchall()
    shares: dict[UUID, dict[str, int]] = {}
    for purchase_id, person_id, weight in conn.execute(
        "select purchase_id, person_id, weight from purchase_share where purchase_id = any(%s)",
        ([r[0] for r in rows],),
    ):
        shares.setdefault(purchase_id, {})[str(person_id)] = weight
    items = [
        InvoiceItem(
            purchase_id=r[0],
            description=r[1],
            purchase_date=r[2],
            installment_number=r[3],
            installments=r[4],
            amount_cents=r[5],
            status=r[6],
            shares=shares[r[0]],
        )
        for r in rows
    ]
    return InvoiceOut(
        payment_method_id=method_id,
        year=year,
        month=month,
        closing_date=closing_date,
        due_date=due_date,
        exists=True,
        total_cents=sum(i.amount_cents for i in items),
        per_person=billing.person_totals((i.amount_cents, i.shares) for i in items),
        pending_count=sum(1 for i in items if i.status == "pendente"),
        items=items,
    )


@router.get("/{method_id}/invoices/current")
def current_invoice(method_id: UUID, conn: Conn) -> InvoiceOut:
    card = _card(conn, method_id)
    invoice = billing.invoice_for(card, dates.today_sp())
    return _build(conn, method_id, card, invoice.year, invoice.month)


@router.get("/{method_id}/invoices/{year}/{month}")
def get_invoice(
    method_id: UUID,
    year: Annotated[int, Path(ge=2000, le=2100)],
    month: Annotated[int, Path(ge=1, le=12)],
    conn: Conn,
) -> InvoiceOut:
    card = _card(conn, method_id)
    return _build(conn, method_id, card, year, month)
