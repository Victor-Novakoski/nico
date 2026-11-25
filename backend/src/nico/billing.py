"""Cálculo de faturas, parcelas e divisão por pessoa (decisões 002 e 004).

Lógica pura, só stdlib. Dinheiro sempre em centavos inteiros, nunca float.
"""

from __future__ import annotations

import calendar
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date


@dataclass(frozen=True)
class Card:
    closing_day: int
    due_day: int

    def __post_init__(self) -> None:
        for name, value in (("closing_day", self.closing_day), ("due_day", self.due_day)):
            if isinstance(value, bool) or not isinstance(value, int) or not 1 <= value <= 31:
                raise ValueError(f"{name} deve estar entre 1 e 31, recebido {value!r}")


@dataclass(frozen=True)
class Invoice:
    year: int  # competência = mês do vencimento
    month: int
    closing_date: date
    due_date: date


def _clamped_date(year: int, month: int, day: int) -> date:
    """Dia maior que o mês vira o último dia do mês (31 em fevereiro -> 28 ou 29)."""
    return date(year, month, min(day, calendar.monthrange(year, month)[1]))


def _add_months(year: int, month: int, n: int) -> tuple[int, int]:
    index = year * 12 + (month - 1) + n
    return index // 12, index % 12 + 1


def _invoice_closing_in(card: Card, year: int, month: int) -> Invoice:
    """Fatura que fecha no mês (year, month); vence no mesmo mês ou no seguinte.

    O mês do vencimento sai dos dias configurados, não das datas ajustadas: assim cada mês
    de fechamento tem uma competência só. Ex.: fecha 28 e vence 31 em fevereiro vira
    fechamento e vencimento em 28/02; comparar as datas ajustadas jogaria o vencimento para
    31/03 e repetiria a competência da fatura de março.
    """
    closing = _clamped_date(year, month, card.closing_day)
    if card.due_day > card.closing_day:
        due = _clamped_date(year, month, card.due_day)
    else:
        due_year, due_month = _add_months(year, month, 1)
        due = _clamped_date(due_year, due_month, card.due_day)
    return Invoice(due.year, due.month, closing, due)


def invoice_for(card: Card, purchase_date: date) -> Invoice:
    """Fatura cujo fechamento é a primeira data de fechamento estritamente maior que a compra.

    Suposição a confirmar com faturas reais: compra no dia do fechamento entra na fatura seguinte.
    """
    invoice = _invoice_closing_in(card, purchase_date.year, purchase_date.month)
    if invoice.closing_date <= purchase_date:
        return next_invoice(card, invoice)
    return invoice


def next_invoice(card: Card, invoice: Invoice, steps: int = 1) -> Invoice:
    """Fatura `steps` faturas à frente (steps >= 0)."""
    if steps < 0:
        raise ValueError("steps não pode ser negativo")
    year, month = _add_months(invoice.closing_date.year, invoice.closing_date.month, steps)
    return _invoice_closing_in(card, year, month)


def split_installments(total_cents: int, n: int) -> list[int]:
    """Divide o total em n parcelas inteiras.

    Suposição a confirmar com faturas reais: o centavo que sobra vai para a primeira parcela.
    """
    if n < 1:
        raise ValueError("n deve ser pelo menos 1")
    if total_cents < 0:
        raise ValueError("total_cents não pode ser negativo")
    base, remainder = divmod(total_cents, n)
    first = base + remainder
    return [first] + [base] * (n - 1)


def installment_schedule(
    card: Card, purchase_date: date, total_cents: int, n: int
) -> list[tuple[Invoice, int]]:
    """Parcela 1 na fatura da compra; as seguintes, uma por fatura."""
    amounts = split_installments(total_cents, n)
    first = invoice_for(card, purchase_date)
    return [(next_invoice(card, first, i), amount) for i, amount in enumerate(amounts)]


def split_by_shares(amount_cents: int, shares: dict[str, int]) -> dict[str, int]:
    """Divide o valor por pesos inteiros positivos; soma exatamente `amount_cents`.

    As sobras vão um centavo por vez, na ordem das chaves ordenadas (determinístico).
    """
    if not shares:
        raise ValueError("shares não pode ser vazio")
    if any(isinstance(w, bool) or not isinstance(w, int) or w <= 0 for w in shares.values()):
        raise ValueError("os pesos devem ser inteiros positivos")
    if amount_cents < 0:
        raise ValueError("amount_cents não pode ser negativo")
    total_weight = sum(shares.values())
    result = {person: amount_cents * w // total_weight for person, w in shares.items()}
    leftover = amount_cents - sum(result.values())
    for person in sorted(shares)[:leftover]:
        result[person] += 1
    return result


def person_totals(items: Iterable[tuple[int, dict[str, int]]]) -> dict[str, int]:
    """Total por pessoa numa fatura, dado (valor da parcela, shares) de cada item."""
    totals: dict[str, int] = {}
    for amount_cents, shares in items:
        for person, cents in split_by_shares(amount_cents, shares).items():
            totals[person] = totals.get(person, 0) + cents
    return totals
