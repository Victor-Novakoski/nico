"""O que todo provedor de extração manda e recebe (decisões 002 e 006).

Lógica pura, sem rede. O prompt só pede trechos da frase: valor, data, meio e pessoa
são conferidos depois em `schema.validate`, nunca calculados pelo modelo.
"""

from __future__ import annotations

import copy
from dataclasses import dataclass, field
from datetime import date
from typing import Any

from nico.ai.schema import Extraction, Method, Person

WEEKDAYS = ["segunda", "terça", "quarta", "quinta", "sexta", "sábado", "domingo"]


@dataclass(frozen=True)
class ExtractionContext:
    """Data de hoje e as listas fechadas da casa, passadas como `context` na cascata."""

    today: date
    methods: list[Method] = field(default_factory=list)
    people: list[Person] = field(default_factory=list)


def _names(values: list[str]) -> str:
    return ", ".join(v.strip() for v in values if v.strip())


def system_prompt(ctx: ExtractionContext) -> str:
    """Instruções fixas mais a data e as listas; nunca leva a frase da pessoa."""
    methods = "\n".join(f"- {_names(m.aliases)} ({m.type})" for m in ctx.methods) or "- nenhum"
    people = "\n".join(f"- {_names(p.names)}" for p in ctx.people) or "- nenhuma"
    weekday = WEEKDAYS[ctx.today.weekday()]
    return (
        "Você lê gastos escritos ou falados em português do Brasil e devolve só JSON "
        "no schema pedido, com uma lista `items` (um item por gasto, mesmo que seja um só).\n"
        "Regras:\n"
        "- Copie o valor e a data exatamente como estão na frase (`amount_text`, "
        "`date_text`). Não calcule, não converta, não some.\n"
        "- Em `method` e `person`, use um dos nomes das listas abaixo quando a frase "
        "indicar; se a frase não diz, deixe null. Não invente.\n"
        "- `installments` só quando a frase diz as parcelas (ex.: 3x).\n"
        "- Campo que a frase não traz fica null.\n"
        f"Hoje é {weekday}, {ctx.today:%d/%m/%Y}.\n"
        f"Meios de pagamento da casa:\n{methods}\n"
        f"Pessoas da casa:\n{people}"
    )


def _inline(node: Any, defs: dict[str, Any]) -> Any:
    if isinstance(node, dict):
        ref = node.get("$ref")
        if isinstance(ref, str) and ref.startswith("#/$defs/"):
            target = copy.deepcopy(defs[ref.removeprefix("#/$defs/")])
            rest = {k: v for k, v in node.items() if k != "$ref"}
            return _inline({**target, **rest}, defs)
        return {k: _inline(v, defs) for k, v in node.items() if k != "$defs"}
    if isinstance(node, list):
        return [_inline(v, defs) for v in node]
    return node


def extraction_schema() -> dict[str, Any]:
    """JSON schema de `Extraction` sem `$ref`/`$defs` (nem todo provedor resolve)."""
    schema = Extraction.model_json_schema()
    return _inline(schema, schema.get("$defs", {}))


def parse_extraction(content: str) -> Extraction:
    """Valida o texto devolvido pelo modelo. JSON ruim levanta `ValidationError`."""
    return Extraction.model_validate_json(content)
