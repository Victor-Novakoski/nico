"""Contas fixas do mês: vencimento, parcela, estimativa e status (decisões 002 e 012).

Lógica pura, só stdlib, sem banco nem rede. Dinheiro sempre em centavos inteiros, nunca float.
"""

from __future__ import annotations

import calendar
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date

PAID = "paga"
TO_PAY = "a_pagar"
ESTIMATE_WINDOW = 3  # quantos pagamentos entram na média


@dataclass(frozen=True)
class Bill:
    id: str
    name: str
    due_day: int
    amount_cents: int | None  # None = "varia"
    method_id: str
    installments_total: int | None = None
    start_year: int | None = None
    start_month: int | None = None
    active: bool = True

    def __post_init__(self) -> None:
        if isinstance(self.due_day, bool) or not 1 <= self.due_day <= 31:
            raise ValueError(f"due_day deve estar entre 1 e 31, recebido {self.due_day!r}")
        if self.amount_cents is not None and self.amount_cents < 0:
            raise ValueError("amount_cents não pode ser negativo")
        has_total = self.installments_total is not None
        if has_total != (self.start_year is not None) or has_total != (
            self.start_month is not None
        ):
            raise ValueError("parcelas exigem total, ano e mês de início juntos")
        if has_total:
            assert self.installments_total is not None and self.start_month is not None
            if self.installments_total < 1:
                raise ValueError("installments_total deve ser pelo menos 1")
            if not 1 <= self.start_month <= 12:
                raise ValueError("start_month deve estar entre 1 e 12")


@dataclass(frozen=True)
class Payment:
    bill_id: str
    year: int  # mês a que a conta pertence (o do vencimento)
    month: int
    amount_cents: int


@dataclass(frozen=True)
class MonthBill:
    bill_id: str
    name: str
    due_date: date
    status: str  # PAID ou TO_PAY
    amount_cents: int | None  # None só quando "varia" e não há histórico
    estimated: bool
    installment_number: int | None = None
    installment_total: int | None = None


def due_date(due_day: int, year: int, month: int) -> date:
    """Vencimento no mês; dia maior que o mês vira o último dia (31 em fevereiro)."""
    if isinstance(due_day, bool) or not 1 <= due_day <= 31:
        raise ValueError(f"due_day deve estar entre 1 e 31, recebido {due_day!r}")
    return date(year, month, min(due_day, calendar.monthrange(year, month)[1]))


def installment_of(
    start_year: int, start_month: int, total: int, year: int, month: int
) -> int | None:
    """Número da parcela (1 a total) no mês, ou None fora do intervalo."""
    number = (year * 12 + month) - (start_year * 12 + start_month) + 1
    return number if 1 <= number <= total else None


def estimate(previous_cents: list[int]) -> int | None:
    """Média inteira dos 3 últimos pagamentos (a lista vem do mais antigo ao mais novo).

    Arredonda para o centavo mais próximo, metade para cima, só com inteiros.
    Sem histórico, None.
    """
    last = previous_cents[-ESTIMATE_WINDOW:]
    if not last:
        return None
    return (2 * sum(last) + len(last)) // (2 * len(last))


def month_bills(
    bills: Iterable[Bill], payments: Iterable[Payment], year: int, month: int
) -> list[MonthBill]:
    """Contas ativas que vencem no mês, ordenadas por vencimento e nome.

    Paga: valor pago. Valor fixo: o fixo. "Varia" sem pagamento: estimativa pela média dos
    3 últimos pagamentos anteriores ao mês (estimated=True; None sem histórico).
    """
    payments = list(payments)
    result: list[MonthBill] = []
    for bill in bills:
        if not bill.active:
            continue
        number: int | None = None
        if bill.installments_total is not None:
            assert bill.start_year is not None and bill.start_month is not None
            number = installment_of(
                bill.start_year, bill.start_month, bill.installments_total, year, month
            )
            if number is None:
                continue
        paid = next(
            (p for p in payments if p.bill_id == bill.id and (p.year, p.month) == (year, month)),
            None,
        )
        if paid is not None:
            status, cents, estimated = PAID, paid.amount_cents, False
        elif bill.amount_cents is not None:
            status, cents, estimated = TO_PAY, bill.amount_cents, False
        else:
            history = sorted(
                (p for p in payments if p.bill_id == bill.id and (p.year, p.month) < (year, month)),
                key=lambda p: (p.year, p.month),
            )
            status, cents, estimated = TO_PAY, estimate([p.amount_cents for p in history]), True
        result.append(
            MonthBill(
                bill_id=bill.id,
                name=bill.name,
                due_date=due_date(bill.due_day, year, month),
                status=status,
                amount_cents=cents,
                estimated=estimated,
                installment_number=number,
                installment_total=bill.installments_total,
            )
        )
    result.sort(key=lambda b: (b.due_date, b.name))
    return result
