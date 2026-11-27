"""Saldo do grupo: quem deve a quem (decisões 008 e 013).

Lógica pura, só stdlib: sem banco e sem IA. Valores em centavos inteiros.
"""

from collections.abc import Iterable
from dataclasses import dataclass

from nico.billing import split_by_shares


@dataclass(frozen=True)
class GroupExpense:
    """Gasto do grupo: `payer` (dono do meio de pagamento) pagou `amount_cents`.

    `shares` são os pesos inteiros por pessoa para dividir o valor.
    """

    payer: str
    amount_cents: int
    shares: dict[str, int]


@dataclass(frozen=True)
class Settlement:
    """Acerto: `from_person` pagou `amount_cents` a `to_person`."""

    from_person: str
    to_person: str
    amount_cents: int


def balances(expenses: Iterable[GroupExpense], settlements: Iterable[Settlement]) -> dict[str, int]:
    """Saldo por pessoa em centavos: positivo = tem a receber, negativo = deve.

    Cada gasto credita o valor a quem pagou e debita a parte de cada membro
    (arredondamento da decisão 008, via `split_by_shares`). Cada acerto soma o
    valor a quem pagou e subtrai de quem recebeu. A soma dos saldos é sempre zero.
    Quem tem saldo 0 continua no dicionário (quem participou aparece).
    """
    result: dict[str, int] = {}

    def add(person: str, cents: int) -> None:
        result[person] = result.get(person, 0) + cents

    for expense in expenses:
        parts = split_by_shares(expense.amount_cents, expense.shares)
        add(expense.payer, expense.amount_cents)
        for person, cents in parts.items():
            add(person, -cents)
    for settlement in settlements:
        if settlement.amount_cents <= 0:
            raise ValueError("o valor do acerto deve ser positivo")
        if settlement.from_person == settlement.to_person:
            raise ValueError("o acerto deve ser entre pessoas diferentes")
        add(settlement.from_person, settlement.amount_cents)
        add(settlement.to_person, -settlement.amount_cents)
    return result


def who_owes_whom(balances: dict[str, int]) -> list[tuple[str, str, int]]:
    """Transferências (de, para, centavos) que zeram o grupo.

    Algoritmo guloso: o maior devedor paga ao maior credor, e repete. Dá no
    máximo n-1 transferências (o mínimo exato é NP-difícil e não é buscado).
    Determinístico: empates se resolvem pelo id em ordem alfabética.
    """
    if sum(balances.values()) != 0:
        raise ValueError("a soma dos saldos deve ser zero")
    debtors = {p: -v for p, v in balances.items() if v < 0}
    creditors = {p: v for p, v in balances.items() if v > 0}
    transfers: list[tuple[str, str, int]] = []
    while debtors and creditors:
        debtor = min(debtors, key=lambda p: (-debtors[p], p))
        creditor = min(creditors, key=lambda p: (-creditors[p], p))
        cents = min(debtors[debtor], creditors[creditor])
        transfers.append((debtor, creditor, cents))
        debtors[debtor] -= cents
        creditors[creditor] -= cents
        if debtors[debtor] == 0:
            del debtors[debtor]
        if creditors[creditor] == 0:
            del creditors[creditor]
    return transfers
