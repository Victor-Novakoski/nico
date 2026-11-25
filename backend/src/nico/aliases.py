"""Reconhece o cartão pelo apelido que a pessoa fala, sem IA (decisão 007).

Lógica pura, só stdlib.
"""

from __future__ import annotations

import re
import unicodedata


def normalize(text: str) -> str:
    """Minúsculas, sem acento, espaços únicos e sem pontuação nas pontas."""
    decomposed = unicodedata.normalize("NFD", text.casefold())
    without_accents = "".join(c for c in decomposed if not unicodedata.combining(c))
    collapsed = " ".join(without_accents.split())
    return collapsed.strip(".,;:!?-_\"'()[]{}/\\ ")


def match_card(text: str, aliases: dict[str, str]) -> str | None:
    """Id do cartão cujo apelido (o mais longo) aparece no texto como palavra inteira.

    Dois cartões diferentes empatados no tamanho do apelido são ambíguos: devolve None
    para a pessoa escolher, nunca chuta. Sem nenhum apelido no texto, também None.
    """
    normalized_text = normalize(text)
    best_length = 0
    best_cards: set[str] = set()
    for alias, card_id in aliases.items():
        normalized_alias = normalize(alias)
        if not normalized_alias or len(normalized_alias) < best_length:
            continue
        pattern = rf"(?<!\w){re.escape(normalized_alias)}(?!\w)"
        if not re.search(pattern, normalized_text):
            continue
        if len(normalized_alias) > best_length:
            best_length = len(normalized_alias)
            best_cards = set()
        best_cards.add(card_id)
    return next(iter(best_cards)) if len(best_cards) == 1 else None
