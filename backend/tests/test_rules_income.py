from datetime import date

import pytest

from nico.rules import ParsedIncome, parse_income

TODAY = date(2026, 3, 18)


def test_recebi_with_method_and_filler():
    assert parse_income("recebi 350 do cliente no pix", TODAY) == ParsedIncome(
        "cliente", 35000, TODAY
    )


@pytest.mark.parametrize(
    ("text", "description", "cents"),
    [
        ("entrou 1.200 do freela", "freela", 120000),
        ("ganhei 80", "", 8000),
        ("caiu 80,50 da venda de bolo", "venda de bolo", 8050),
        ("recebi R$ 1.200,50 de aluguel", "aluguel", 120050),
    ],
)
def test_each_verb_and_value_format(text, description, cents):
    result = parse_income(text, TODAY)
    assert result is not None
    assert (result.description, result.amount_cents, result.received_date) == (
        description,
        cents,
        TODAY,
    )


def test_relative_date():
    result = parse_income("recebi 50 do vizinho ontem", TODAY)
    assert result == ParsedIncome("vizinho", 5000, date(2026, 3, 17))


def test_day_of_month():
    result = parse_income("entrou 900 da bolsa dia 5", TODAY)
    assert result == ParsedIncome("bolsa", 90000, date(2026, 3, 5))


@pytest.mark.parametrize(
    "text",
    [
        "gastei 120 no mercado",
        "15 de pao no debito",
        "recebi do cliente",
        "recebi 100 e 200 do cliente",
        "recebi 100 ontem e hoje",
        "",
    ],
)
def test_not_income_or_ambiguous_returns_none(text):
    assert parse_income(text, TODAY) is None
