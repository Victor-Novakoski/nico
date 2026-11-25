"""Casos dos evals da IA (decisão 005): frase, listas fechadas e rascunho esperado.

Sem rede e sem banco. O arquivo é JSONL, um caso por linha. O rascunho esperado é o
que `schema.validate` devolve a partir de uma extração correta: centavos, datas e ids
já calculados pelo código, nunca o que o modelo escreveu.
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

from pydantic import BaseModel, ConfigDict, ValidationError

from nico.ai.prompt import ExtractionContext
from nico.ai.schema import Method, MethodType, Person


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class EvalMethod(_Strict):
    id: str
    aliases: list[str]
    type: MethodType


class EvalPerson(_Strict):
    id: str
    names: list[str]


class ExpectedDraft(_Strict):
    """Rascunho esperado. `description` é só uma dica curta (comparação aproximada)."""

    description: str | None = None
    amount_cents: int | None = None
    method_id: str | None = None
    purchase_date: date | None = None
    installments: int = 1
    person_id: str | None = None


class EvalCase(_Strict):
    id: str
    text: str
    today: date
    methods: list[EvalMethod]
    people: list[EvalPerson]
    expected: list[ExpectedDraft]
    tags: list[str] = []


def load_cases(path: Path | str) -> list[EvalCase]:
    """Lê um JSONL de casos. Linhas em branco são ignoradas; erro cita o número da linha."""
    cases: list[EvalCase] = []
    with Path(path).open(encoding="utf-8") as handle:
        for number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            try:
                cases.append(EvalCase.model_validate(json.loads(line)))
            except json.JSONDecodeError as exc:
                raise ValueError(f"{path}:{number}: JSON inválido: {exc}") from exc
            except ValidationError as exc:
                raise ValueError(f"{path}:{number}: caso inválido: {exc}") from exc
    return cases


def to_context(case: EvalCase) -> ExtractionContext:
    """Monta o contexto que os provedores recebem (data de hoje e listas fechadas)."""
    return ExtractionContext(
        today=case.today,
        methods=[Method(id=m.id, aliases=list(m.aliases), type=m.type) for m in case.methods],
        people=[Person(id=p.id, names=list(p.names)) for p in case.people],
    )
