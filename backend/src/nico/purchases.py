"""Gravar compra com faturas, parcelas e divisão por pessoa (decisões 004, 008, 009 e 010).

SQL com psycopg sobre uma conexão aberta. Nada aqui faz commit: a transação é de quem chama.
Valores, datas e parcelas vêm do `billing`, nunca da IA (decisão 002).
"""

from __future__ import annotations

from datetime import date
from typing import Any
from uuid import UUID

import psycopg

from nico import billing

CASH_KINDS = ("debito", "pix", "dinheiro")
STATUSES = ("pendente", "conferido")


def _find_or_create_invoice(
    conn: psycopg.Connection, payment_method_id: UUID, invoice: billing.Invoice
) -> UUID:
    """Fatura do cartão no mês; se já existe, mantém as datas gravadas (decisão 004)."""
    params = (payment_method_id, invoice.year, invoice.month)
    select = "select id from invoice where payment_method_id = %s and year = %s and month = %s"
    row = conn.execute(select, params).fetchone()
    if row:
        return row[0]
    row = conn.execute(
        "insert into invoice (payment_method_id, year, month, closing_date, due_date)"
        " values (%s, %s, %s, %s, %s) on conflict (payment_method_id, year, month) do nothing"
        " returning id",
        (*params, invoice.closing_date, invoice.due_date),
    ).fetchone()
    if row:
        return row[0]
    return conn.execute(select, params).fetchone()[0]


def _schedule(
    conn: psycopg.Connection,
    payment_method_id: UUID,
    purchase_date: date,
    total_cents: int,
    installments: int,
) -> list[tuple[billing.Invoice, int]]:
    """Parcelas (vazio à vista); `ValueError` se o meio não existe ou é à vista parcelado."""
    method = conn.execute(
        "select kind, closing_day, due_day from payment_method where id = %s",
        (payment_method_id,),
    ).fetchone()
    if method is None:
        raise ValueError(f"meio de pagamento desconhecido: {payment_method_id}")
    kind, closing_day, due_day = method
    if kind in CASH_KINDS and installments != 1:
        raise ValueError("compra à vista não tem parcelas (installments deve ser 1)")
    if kind != "credito":
        return []
    return billing.installment_schedule(
        billing.Card(closing_day, due_day), purchase_date, total_cents, installments
    )


def _insert_installments(
    conn: psycopg.Connection,
    purchase_id: UUID,
    payment_method_id: UUID,
    schedule: list[tuple[billing.Invoice, int]],
) -> None:
    for number, (invoice, amount) in enumerate(schedule, start=1):
        invoice_id = _find_or_create_invoice(conn, payment_method_id, invoice)
        conn.execute(
            "insert into installment (purchase_id, invoice_id, number, amount_cents)"
            " values (%s, %s, %s, %s)",
            (purchase_id, invoice_id, number, amount),
        )


def _insert_shares(conn: psycopg.Connection, purchase_id: UUID, shares: dict[UUID, int]) -> None:
    for person_id, weight in shares.items():
        conn.execute(
            "insert into purchase_share (purchase_id, person_id, weight) values (%s, %s, %s)",
            (purchase_id, person_id, weight),
        )


def create_purchase(
    conn: psycopg.Connection,
    *,
    id: UUID,
    payment_method_id: UUID,
    description: str,
    total_cents: int,
    purchase_date: date,
    installments: int,
    created_by_person_id: UUID,
    shares: dict[UUID, int] | None = None,
    status: str = "pendente",
    ai_provider: str | None = None,
    group_id: UUID | None = None,
) -> UUID:
    """Grava a compra e devolve o `id`. Não faz commit.

    Crédito: cria (ou reaproveita, com as datas já gravadas) a fatura de cada parcela e grava
    as parcelas 1..n. À vista (débito, Pix, dinheiro): sem fatura e sem parcelas; `installments`
    diferente de 1 levanta `ValueError`. `shares` vazio ou `None` vira a pessoa que lançou, peso 1
    (decisão 009).

    Idempotente pelo `id`: reenviar o mesmo `id` devolve a compra existente sem inserir nada. O
    reenvio não é comparado com o original; se os dados mudaram, ficam os primeiros.
    """
    if isinstance(total_cents, bool) or not isinstance(total_cents, int) or total_cents < 0:
        raise ValueError("total_cents deve ser um inteiro >= 0")
    if isinstance(installments, bool) or not isinstance(installments, int) or installments < 1:
        raise ValueError("installments deve ser um inteiro >= 1")
    if status not in STATUSES:
        raise ValueError(f"status deve ser um de {STATUSES}, recebido {status!r}")
    shares = dict(shares) if shares else {created_by_person_id: 1}
    if any(isinstance(w, bool) or not isinstance(w, int) or w <= 0 for w in shares.values()):
        raise ValueError("os pesos devem ser inteiros positivos")

    schedule = _schedule(conn, payment_method_id, purchase_date, total_cents, installments)

    inserted = conn.execute(
        "insert into purchase (id, description, total_cents, purchase_date, installments,"
        " status, ai_provider, payment_method_id, created_by_person_id, group_id)"
        " values (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s) on conflict (id) do nothing returning id",
        (
            id,
            description,
            total_cents,
            purchase_date,
            installments,
            status,
            ai_provider,
            payment_method_id,
            created_by_person_id,
            group_id,
        ),
    ).fetchone()
    if inserted is None:
        return id

    _insert_installments(conn, id, payment_method_id, schedule)
    _insert_shares(conn, id, shares)
    return id


def get_purchase(conn: psycopg.Connection, id: UUID) -> dict[str, Any] | None:
    """Compra com `installments_list` (e a fatura de cada uma) e `shares`; `None` se não existe.

    As parcelas saem por número; `shares` é `{person_id: weight}`.
    """
    row = conn.execute(
        "select id, description, total_cents, purchase_date, installments, status, ai_provider,"
        " payment_method_id, created_by_person_id, group_id from purchase where id = %s",
        (id,),
    ).fetchone()
    if row is None:
        return None
    keys = (
        "id",
        "description",
        "total_cents",
        "purchase_date",
        "installments",
        "status",
        "ai_provider",
        "payment_method_id",
        "created_by_person_id",
        "group_id",
    )
    result: dict[str, Any] = dict(zip(keys, row, strict=True))
    result["installments_list"] = [
        {
            "number": n,
            "amount_cents": amount,
            "invoice_id": invoice_id,
            "year": year,
            "month": month,
            "closing_date": closing,
            "due_date": due,
        }
        for n, amount, invoice_id, year, month, closing, due in conn.execute(
            "select i.number, i.amount_cents, v.id, v.year, v.month, v.closing_date, v.due_date"
            " from installment i join invoice v on v.id = i.invoice_id"
            " where i.purchase_id = %s order by i.number",
            (id,),
        )
    ]
    result["shares"] = dict(
        conn.execute(
            "select person_id, weight from purchase_share where purchase_id = %s", (id,)
        ).fetchall()
    )
    return result


REBUILD_FIELDS = ("total_cents", "payment_method_id", "purchase_date", "installments")
PLAIN_FIELDS = ("description", "status")


def update_purchase(conn: psycopg.Connection, id: UUID, **changes: Any) -> bool:
    """Edição parcial; `False` se a compra não existe. Não faz commit.

    Aceita `description`, `status`, `total_cents`, `payment_method_id`, `purchase_date`,
    `installments` e `shares` (`{person_id: weight}`; vazio vira quem lançou, peso 1). Mudar
    valor, meio, data ou parcelas apaga as parcelas e as refaz, reaproveitando faturas já
    existentes (que mantêm as datas gravadas, decisão 004); faturas que ficam sem parcela não
    são apagadas. As mesmas validações da criação valem aqui (`ValueError`).
    """
    unknown = set(changes) - {*REBUILD_FIELDS, *PLAIN_FIELDS, "shares"}
    if unknown:
        raise ValueError(f"campos desconhecidos: {sorted(unknown)}")
    row = conn.execute(
        "select description, total_cents, purchase_date, installments, status,"
        " payment_method_id, created_by_person_id from purchase where id = %s for update",
        (id,),
    ).fetchone()
    if row is None:
        return False
    current = dict(
        zip(
            (
                "description",
                "total_cents",
                "purchase_date",
                "installments",
                "status",
                "payment_method_id",
                "created_by_person_id",
            ),
            row,
            strict=True,
        )
    )
    merged = {**current, **{k: v for k, v in changes.items() if k != "shares"}}
    if merged["status"] not in STATUSES:
        raise ValueError(f"status deve ser um de {STATUSES}, recebido {merged['status']!r}")
    shares = changes.get("shares")
    if shares is not None:
        shares = dict(shares) if shares else {current["created_by_person_id"]: 1}
        if any(isinstance(w, bool) or not isinstance(w, int) or w <= 0 for w in shares.values()):
            raise ValueError("os pesos devem ser inteiros positivos")

    rebuild = any(k in changes and changes[k] != current[k] for k in REBUILD_FIELDS)
    schedule = _schedule(
        conn,
        merged["payment_method_id"],
        merged["purchase_date"],
        merged["total_cents"],
        merged["installments"],
    )
    conn.execute(
        "update purchase set description = %s, total_cents = %s, purchase_date = %s,"
        " installments = %s, status = %s, payment_method_id = %s where id = %s",
        (
            merged["description"],
            merged["total_cents"],
            merged["purchase_date"],
            merged["installments"],
            merged["status"],
            merged["payment_method_id"],
            id,
        ),
    )
    if rebuild:
        conn.execute("delete from installment where purchase_id = %s", (id,))
        _insert_installments(conn, id, merged["payment_method_id"], schedule)
    if shares is not None:
        conn.execute("delete from purchase_share where purchase_id = %s", (id,))
        _insert_shares(conn, id, shares)
    return True
