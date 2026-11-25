"""Leitura de datas relativas em pt-BR, no fuso de São Paulo (decisão 002).

Lógica pura, só stdlib. A data sai daqui, nunca do modelo de IA.
"""

from __future__ import annotations

import re
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

_SP = ZoneInfo("America/Sao_Paulo")

_WORDS = {"hoje": 0, "ontem": 1, "anteontem": 2}
_WORD_RE = re.compile(r"\b(hoje|ontem|anteontem)\b")
_NUMERIC_RE = re.compile(r"(?<![\d/])(\d{1,2})/(\d{1,2})(?:/(\d{4}|\d{2}))?(?![\d/])")
_DAY_RE = re.compile(r"\bdia\s+(\d{1,2})\b")


def today_sp() -> date:
    """Data de hoje em São Paulo (independe do fuso da máquina)."""
    return datetime.now(_SP).date()


def _previous_month(year: int, month: int) -> tuple[int, int]:
    return (year - 1, 12) if month == 1 else (year, month - 1)


def parse_date_pt(text: str, today: date) -> date | None:
    """Converte uma data escrita em pt-BR em `date`; `None` se o texto não tem data.

    Aceita `hoje`, `ontem`, `anteontem`, `dia 10`, `10/11`, `10/11/2026` e `10/11/26`.
    Datas sem ano e `dia N` nunca caem no futuro: voltam ao mês ou ao ano anterior.
    Data inexistente (31/02) levanta `ValueError`.
    """
    text = text.lower()

    match = _NUMERIC_RE.search(text)
    if match:
        day, month = int(match.group(1)), int(match.group(2))
        year_text = match.group(3)
        if year_text is not None:
            year = int(year_text)
            if len(year_text) == 2:
                year += 2000
            return date(year, month, day)
        result = date(today.year, month, day)
        if result > today:
            result = date(today.year - 1, month, day)
        return result

    match = _WORD_RE.search(text)
    if match:
        return today - timedelta(days=_WORDS[match.group(1)])

    match = _DAY_RE.search(text)
    if match:
        day = int(match.group(1))
        year, month = today.year, today.month
        if day > today.day:
            year, month = _previous_month(year, month)
        return date(year, month, day)

    return None
