"""Entende frases curtas de gasto sem IA (decisão 007).

Lógica pura, só stdlib. Reutiliza `parse_brl`, `parse_date_pt` e `match_card`.
Na dúvida (valor ausente ou ambíguo, data inválida), devolve `None`: a frase vai
para o formulário ou para a IA.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date

from nico.aliases import match_card, normalize
from nico.dates import parse_date_pt
from nico.money import parse_brl

_INSTALLMENT_RE = re.compile(r"\b(\d{1,2})\s*x\b", re.IGNORECASE)
_PARCEL_RE = re.compile(r"\bparcela\s+(\d{1,2})\s*/\s*(\d{1,2})(?![\d/])", re.IGNORECASE)
_SLASH_RE = re.compile(r"(?<![\d/])(\d{1,2})/(\d{1,2})(?:/(?:\d{4}|\d{2}))?(?![\d/])")
_WORD_DATE_RE = re.compile(r"\b(?:hoje|ontem|anteontem)\b", re.IGNORECASE)
_DAY_RE = re.compile(r"\bdia\s+\d{1,2}\b", re.IGNORECASE)
_MONEY_RE = re.compile(r"^(?:r\$)?\d[\d.]*(?:,\d+)?$", re.IGNORECASE)
_EDGE_CHARS = ".,;:!?-_\"'()[]{}"
_FILLERS = {"de", "do", "da", "no", "na", "em", "com", "pelo", "pela", "a", "o", "e"}
# Verbos com que a pessoa costuma começar a frase ("gastei 120 no mercado").
_LEADING_VERBS = {"gastei", "paguei", "comprei"}


@dataclass
class Draft:
    description: str
    amount_cents: int
    card_id: str | None
    purchase_date: date
    installments: int = 1
    missing: list[str] = field(default_factory=list)


def parse_simple(text: str, aliases: dict[str, str], today: date) -> list[Draft] | None:
    """Um gasto por linha ou separado por `;`. `None` se alguma parte não for entendida."""
    segments = [s.strip() for s in re.split(r"[\n;]", text) if s.strip()]
    if not segments:
        return None
    drafts: list[Draft] = []
    for segment in segments:
        draft = _parse_segment(segment, aliases, today)
        if draft is None:
            return None
        drafts.append(draft)
    return drafts


def _parse_segment(segment: str, aliases: dict[str, str], today: date) -> Draft | None:
    rest = segment
    installments = 1

    # "parcela N/M" é compra em andamento: não se sabe se o valor é o total ou o da
    # parcela, então não chuta (decisão 002) e a linha vai para formulário ou IA.
    if _PARCEL_RE.search(rest):
        return None

    times = _INSTALLMENT_RE.findall(rest)
    if len(times) > 1:
        return None
    if times:
        installments = int(times[0])
        if installments < 1:
            return None
        rest = _INSTALLMENT_RE.sub(" ", rest)

    date_hits = (
        len(_SLASH_RE.findall(rest)) + len(_WORD_DATE_RE.findall(rest)) + len(_DAY_RE.findall(rest))
    )
    if date_hits > 1:
        return None
    try:
        parsed_date = parse_date_pt(rest, today)
    except ValueError:
        return None
    for pattern in (_SLASH_RE, _WORD_DATE_RE, _DAY_RE):
        rest = pattern.sub(" ", rest)

    card_id = match_card(rest, aliases)
    card_words: set[str] = set()
    if card_id is not None:
        normalized_rest = normalize(rest)
        for alias, alias_card in aliases.items():
            alias_norm = normalize(alias)
            if alias_card == card_id and alias_norm:
                if re.search(rf"(?<!\w){re.escape(alias_norm)}(?!\w)", normalized_rest):
                    card_words.update(alias_norm.split())

    tokens = [t for t in rest.split() if normalize(t) not in card_words]
    amount_cents = None
    description_tokens: list[str] = []
    index = 0
    while index < len(tokens):
        token = tokens[index].strip(_EDGE_CHARS.replace("$", ""))
        lowered = token.lower()
        if lowered == "r$" and index + 1 < len(tokens):
            token = "R$" + tokens[index + 1].strip(_EDGE_CHARS)
            index += 1
        if _MONEY_RE.match(token):
            if index + 1 < len(tokens) and normalize(tokens[index + 1]) in {"reais", "real"}:
                index += 1
            if amount_cents is not None:
                return None  # dois valores na mesma linha: ambíguo
            try:
                amount_cents = parse_brl(token)
            except ValueError:
                return None
        else:
            description_tokens.append(tokens[index])
        index += 1
    if not amount_cents:
        return None

    while description_tokens and normalize(description_tokens[0]) in _LEADING_VERBS | _FILLERS:
        description_tokens.pop(0)
    while description_tokens and normalize(description_tokens[-1]) in _FILLERS:
        description_tokens.pop()
    description = " ".join(description_tokens).strip(_EDGE_CHARS + " ")

    missing = []
    if not description:
        missing.append("description")
    if card_id is None:
        missing.append("card_id")
    return Draft(
        description=description,
        amount_cents=amount_cents,
        card_id=card_id,
        purchase_date=parsed_date or today,
        installments=installments,
        missing=missing,
    )


# Entrada de dinheiro (renda): verbo + valor + descrição, sem cartão nem parcelas.
_INCOME_VERBS = {"recebi", "entrou", "ganhei", "caiu"}
# Meios de recebimento: saem da descrição ("recebi 350 do cliente no pix" -> "cliente").
_INCOME_METHODS = {"pix", "ted", "doc", "transferencia", "dinheiro", "especie", "boleto"}


@dataclass
class ParsedIncome:
    description: str
    amount_cents: int
    received_date: date


def parse_income(text: str, today: date) -> ParsedIncome | None:
    """Uma entrada de dinheiro ("recebi 350 do cliente no pix"). `None` se não for entrada
    ou se for ambíguo (sem valor, dois valores, duas datas). Só tira palavras de meio de
    recebimento (pix, ted...) e conectivos da descrição; o resto fica como a pessoa disse."""
    rest = text.strip()
    if not rest or re.search(r"[\n;]", rest):
        return None
    date_hits = (
        len(_SLASH_RE.findall(rest)) + len(_WORD_DATE_RE.findall(rest)) + len(_DAY_RE.findall(rest))
    )
    if date_hits > 1:
        return None
    try:
        parsed_date = parse_date_pt(rest, today)
    except ValueError:
        return None
    for pattern in (_SLASH_RE, _WORD_DATE_RE, _DAY_RE):
        rest = pattern.sub(" ", rest)

    tokens = rest.split()
    if not any(normalize(t.strip(_EDGE_CHARS)) in _INCOME_VERBS for t in tokens):
        return None
    amount_cents = None
    description_tokens: list[str] = []
    index = 0
    while index < len(tokens):
        token = tokens[index].strip(_EDGE_CHARS.replace("$", ""))
        if token.lower() == "r$" and index + 1 < len(tokens):
            token = "R$" + tokens[index + 1].strip(_EDGE_CHARS)
            index += 1
        if _MONEY_RE.match(token):
            if index + 1 < len(tokens) and normalize(tokens[index + 1]) in {"reais", "real"}:
                index += 1
            if amount_cents is not None:
                return None  # dois valores: ambíguo
            try:
                amount_cents = parse_brl(token)
            except ValueError:
                return None
        else:
            description_tokens.append(tokens[index])
        index += 1
    if not amount_cents:
        return None

    # Tira o verbo e o meio ("no pix") de qualquer lugar; conectivos só das pontas,
    # como no parser de gastos ("venda de bolo" fica inteiro).
    kept: list[str] = []
    for token in description_tokens:
        word = normalize(token.strip(_EDGE_CHARS))
        if word in _INCOME_VERBS:
            continue
        if word in _INCOME_METHODS:
            if kept and normalize(kept[-1]) in _FILLERS:
                kept.pop()
            continue
        kept.append(token)
    description_tokens = kept
    while description_tokens and normalize(description_tokens[0]) in _FILLERS:
        description_tokens.pop(0)
    while description_tokens and normalize(description_tokens[-1]) in _FILLERS:
        description_tokens.pop()
    description = " ".join(description_tokens).strip(_EDGE_CHARS + " ")
    return ParsedIncome(
        description=description,
        amount_cents=amount_cents,
        received_date=parsed_date or today,
    )
