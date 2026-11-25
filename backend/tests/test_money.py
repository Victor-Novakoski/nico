import pytest

from nico.money import format_brl, parse_brl


@pytest.mark.parametrize(
    ("text", "cents"),
    [
        ("120", 12000),
        ("120,50", 12050),
        ("15,5", 1550),
        ("1.234,56", 123456),
        ("1.234", 123400),
        ("R$ 15", 1500),
        ("R$15,00", 1500),
        ("r$ 15", 1500),
        ("15 reais", 1500),
        ("1 real", 100),
        ("0,99", 99),
        ("0", 0),
        ("  42  ", 4200),
        ("1.234.567,89", 123456789),
    ],
)
def test_parse_accepted(text, cents):
    assert parse_brl(text) == cents


@pytest.mark.parametrize(
    "text",
    [
        "",
        "   ",
        "-5",
        "-5,00",
        "R$ -5",
        "abc",
        "R$",
        "reais",
        "1,234",
        "1,234.56",
        "1.234.56",
        "12.50",
        "15,999",
        "15,",
        ",50",
        "1 2",
    ],
)
def test_parse_rejected(text):
    with pytest.raises(ValueError):
        parse_brl(text)


def test_parse_rejects_non_string():
    with pytest.raises(ValueError):
        parse_brl(None)  # type: ignore[arg-type]


@pytest.mark.parametrize(
    ("cents", "text"),
    [
        (0, "R$ 0,00"),
        (99, "R$ 0,99"),
        (1500, "R$ 15,00"),
        (123456, "R$ 1.234,56"),
        (123456789, "R$ 1.234.567,89"),
    ],
)
def test_format(cents, text):
    assert format_brl(cents) == text


@pytest.mark.parametrize("cents", [-1, 1.5, True])
def test_format_rejects_invalid(cents):
    with pytest.raises(ValueError):
        format_brl(cents)


@pytest.mark.parametrize("text", ["120", "120,50", "15,5", "1.234,56", "R$ 15", "0,99"])
def test_roundtrip(text):
    cents = parse_brl(text)
    assert parse_brl(format_brl(cents)) == cents
