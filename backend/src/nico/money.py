"""Valor em reais escrito em pt-BR <-> centavos inteiros (decisão 002).

Lógica pura, só stdlib. Dinheiro sempre em centavos inteiros, nunca float.
"""

from __future__ import annotations

import re

_BRL_RE = re.compile(
    r"""
    ^
    (?:r\$\s*)?                       # prefixo opcional: R$ 15, R$15
    (?P<int>\d{1,3}(?:\.\d{3})+|\d+)  # inteiro, com ponto de milhar opcional
    (?:,(?P<frac>\d+))?               # vírgula decimal opcional
    (?:\s*(?:reais|real))?            # sufixo opcional: 15 reais
    $
    """,
    re.VERBOSE | re.IGNORECASE,
)


def parse_brl(text: str) -> int:
    """Converte um valor escrito em reais (pt-BR) em centavos inteiros.

    Aceita `120`, `120,50`, `15,5`, `1.234,56`, `R$ 15`, `R$15,00`, `15 reais`, `0,99`.
    Recusa vazio, negativo, texto sem número, mais de 2 casas decimais e o formato
    americano (`1,234.56`) com ValueError.
    """
    if not isinstance(text, str):
        raise ValueError(f"valor inválido: {text!r}")
    match = _BRL_RE.match(text.strip())
    if match is None:
        raise ValueError(f"valor em reais inválido: {text!r}")
    frac = match.group("frac") or ""
    if len(frac) > 2:
        raise ValueError(f"no máximo 2 casas decimais: {text!r}")
    reais = int(match.group("int").replace(".", ""))
    return reais * 100 + int(frac.ljust(2, "0") or "0")


def format_brl(cents: int) -> str:
    """Formata centavos como `R$ 1.234,56`."""
    if isinstance(cents, bool) or not isinstance(cents, int):
        raise ValueError(f"cents deve ser int, recebido {cents!r}")
    if cents < 0:
        raise ValueError("cents não pode ser negativo")
    reais, rest = divmod(cents, 100)
    return f"R$ {reais:,}".replace(",", ".") + f",{rest:02d}"
