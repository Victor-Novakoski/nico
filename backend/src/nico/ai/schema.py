"""O que a IA devolve e a conferência no código (decisão 002).

Sem rede, sem banco, sem provedor: só recebe uma `Extraction` já pronta. A IA só
extrai trechos; valor, data, meio e pessoa saem daqui, de listas fechadas.

O `Draft` de `rules.py` não serve: exige valor e data e não guarda origem por campo
nem pessoa. Por isso `AiDraft` é próprio e deixa o valor ausente quando não valida.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Literal

from pydantic import BaseModel, Field

from nico.aliases import match_card, normalize
from nico.dates import parse_date_pt
from nico.money import parse_brl

MethodType = Literal["credito", "debito", "pix", "dinheiro"]
Source = Literal["frase", "padrao", "ia"]


class ExtractedItem(BaseModel):
    """Um gasto como a IA leu na frase. Qualquer campo pode vir vazio."""

    description: str | None = Field(None, description="O que foi comprado, em poucas palavras")
    amount_text: str | None = Field(
        None, description="Trecho literal da frase com o valor, exatamente como escrito"
    )
    method: str | None = Field(
        None, description="Meio de pagamento como a frase diz; vazio se a frase não diz"
    )
    installments: int | None = Field(None, description="Número de parcelas, se a frase diz")
    date_text: str | None = Field(
        None, description="Trecho literal da frase com a data (hoje, ontem, dia 10, 10/11)"
    )
    person: str | None = Field(None, description="De quem é o gasto, se a frase diz")


class Extraction(BaseModel):
    """Resposta da IA: sempre uma lista, mesmo com um gasto só."""

    items: list[ExtractedItem] = Field(default_factory=list)


@dataclass(frozen=True)
class Method:
    """Meio de pagamento da casa (lista fechada)."""

    id: str
    aliases: list[str]
    type: MethodType


@dataclass(frozen=True)
class Person:
    """Pessoa da casa (lista fechada)."""

    id: str
    names: list[str]


@dataclass
class AiDraft:
    description: str | None
    amount_cents: int | None
    method_id: str | None
    method_type: MethodType | None
    purchase_date: date | None
    installments: int
    person_id: str | None
    sources: dict[str, Source] = field(default_factory=dict)
    missing: list[str] = field(default_factory=list)


def _blank(text: str | None) -> bool:
    return text is None or not text.strip()


def _closed_id(text: str | None, aliases: dict[str, str]) -> str | None:
    if _blank(text):
        return None
    return match_card(text, aliases)


def validate(
    extraction: Extraction,
    methods: list[Method],
    people: list[Person],
    today: date,
) -> list[AiDraft]:
    """Confere cada item no código. O que não validar fica vazio e vai em `missing`."""
    method_aliases = {a: m.id for m in methods for a in m.aliases if normalize(a)}
    method_types = {m.id: m.type for m in methods}
    person_aliases = {n: p.id for p in people for n in p.names if normalize(n)}
    return [
        _validate_item(item, method_aliases, method_types, person_aliases, today)
        for item in extraction.items
    ]


def _validate_item(
    item: ExtractedItem,
    method_aliases: dict[str, str],
    method_types: dict[str, MethodType],
    person_aliases: dict[str, str],
    today: date,
) -> AiDraft:
    missing: list[str] = []
    sources: dict[str, Source] = {}

    description = None if _blank(item.description) else item.description.strip()
    if description is None:
        missing.append("description")

    amount_cents = None
    if not _blank(item.amount_text):
        try:
            amount_cents = parse_brl(item.amount_text) or None
        except ValueError:
            amount_cents = None
    if amount_cents is None:
        missing.append("amount")

    method_id = _closed_id(item.method, method_aliases)
    method_type = method_types.get(method_id) if method_id is not None else None
    if method_id is None:
        missing.append("method_id")

    purchase_date: date | None
    if _blank(item.date_text):
        purchase_date = today
        sources["purchase_date"] = "padrao"
    else:
        try:
            purchase_date = parse_date_pt(item.date_text, today)
        except ValueError:
            purchase_date = None
        if purchase_date is None:
            missing.append("purchase_date")

    installments = 1
    if item.installments is not None:
        if item.installments < 1:
            missing.append("installments")
        elif item.installments > 1 and method_type in ("debito", "pix", "dinheiro"):
            missing.append("installments")  # decisão 010: "Nx" à vista não vira parcelas
        else:
            installments = item.installments
    else:
        sources["installments"] = "padrao"

    person_id = _closed_id(item.person, person_aliases)
    if person_id is None:
        missing.append("person_id")

    for name in (
        "description",
        "amount",
        "method_id",
        "method_type",
        "purchase_date",
        "installments",
        "person_id",
    ):
        sources.setdefault(name, "ia")
    return AiDraft(
        description=description,
        amount_cents=amount_cents,
        method_id=method_id,
        method_type=method_type,
        purchase_date=purchase_date,
        installments=installments,
        person_id=person_id,
        sources=sources,
        missing=missing,
    )
