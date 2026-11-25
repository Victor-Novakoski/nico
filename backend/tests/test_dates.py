from datetime import date

import pytest

from nico.dates import parse_date_pt, today_sp

TODAY = date(2026, 11, 25)


def test_today_sp_returns_a_date():
    assert isinstance(today_sp(), date)


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("hoje", date(2026, 11, 25)),
        ("Hoje", date(2026, 11, 25)),
        ("ontem", date(2026, 11, 24)),
        ("anteontem", date(2026, 11, 23)),
        ("15 de pão ontem", date(2026, 11, 24)),
    ],
)
def test_relative_words(text, expected):
    assert parse_date_pt(text, TODAY) == expected


def test_relative_words_cross_month_and_year():
    assert parse_date_pt("ontem", date(2026, 3, 1)) == date(2026, 2, 28)
    assert parse_date_pt("anteontem", date(2026, 1, 1)) == date(2025, 12, 30)
    assert parse_date_pt("ontem", date(2024, 3, 1)) == date(2024, 2, 29)


def test_day_of_current_month():
    assert parse_date_pt("dia 10", TODAY) == date(2026, 11, 10)
    assert parse_date_pt("dia 25", TODAY) == date(2026, 11, 25)


def test_day_not_yet_reached_goes_to_previous_month():
    assert parse_date_pt("dia 30", TODAY) == date(2026, 10, 30)
    assert parse_date_pt("dia 10", date(2026, 11, 5)) == date(2026, 10, 10)


def test_day_not_yet_reached_in_january_goes_to_previous_year():
    assert parse_date_pt("dia 20", date(2026, 1, 5)) == date(2025, 12, 20)


def test_day_missing_in_previous_month_is_invalid():
    with pytest.raises(ValueError):
        parse_date_pt("dia 31", date(2026, 3, 5))


def test_day_month_uses_year_of_today():
    assert parse_date_pt("10/11", TODAY) == date(2026, 11, 10)
    assert parse_date_pt("25/11", TODAY) == date(2026, 11, 25)
    assert parse_date_pt("1/2", TODAY) == date(2026, 2, 1)


def test_day_month_in_the_future_goes_to_previous_year():
    assert parse_date_pt("26/11", TODAY) == date(2025, 11, 26)
    assert parse_date_pt("10/12", date(2026, 1, 3)) == date(2025, 12, 10)


def test_full_date_four_and_two_digit_year():
    assert parse_date_pt("10/11/2026", TODAY) == date(2026, 11, 10)
    assert parse_date_pt("10/11/26", TODAY) == date(2026, 11, 10)
    assert parse_date_pt("05/03/2025", TODAY) == date(2025, 3, 5)


def test_date_inside_a_sentence():
    assert parse_date_pt("120 no mercado dia 10", TODAY) == date(2026, 11, 10)
    assert parse_date_pt("gastei 15 no débito em 10/11", TODAY) == date(2026, 11, 10)


@pytest.mark.parametrize("text", ["", "   ", "120 no mercado", "15 de pão no débito", "em 3x"])
def test_text_without_date_returns_none(text):
    assert parse_date_pt(text, TODAY) is None


@pytest.mark.parametrize("text", ["31/02", "31/02/2026", "29/02/2026", "10/13", "dia 32", "0/5"])
def test_invalid_date_raises(text):
    with pytest.raises(ValueError):
        parse_date_pt(text, TODAY)


def test_leap_day_valid_in_leap_year():
    assert parse_date_pt("29/02/2024", TODAY) == date(2024, 2, 29)
    assert parse_date_pt("29/02/28", TODAY) == date(2028, 2, 29)
