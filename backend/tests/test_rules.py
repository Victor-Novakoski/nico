from datetime import date

from nico.rules import Draft, parse_simple

TODAY = date(2026, 11, 25)
ALIASES = {"roxinho": "card-a", "cartao azul": "card-b", "debito": "card-c"}


def one(text):
    drafts = parse_simple(text, ALIASES, TODAY)
    assert drafts is not None and len(drafts) == 1
    return drafts[0]


def test_amount_description_card_and_installments():
    assert one("120 mercado roxinho 3x") == Draft("mercado", 12000, "card-a", TODAY, 3, [])


def test_leading_verb_and_fillers_leave_the_description():
    assert one("gastei 120 no mercado roxinho 3x").description == "mercado"
    assert one("paguei 30 de uber").description == "uber"


def test_decimal_amount_card_and_relative_date():
    assert one("15,50 pão débito ontem") == Draft("pão", 1550, "card-c", date(2026, 11, 24), 1, [])


def test_without_card_marks_missing():
    draft = one("30 padaria")
    assert draft.card_id is None
    assert draft.missing == ["card_id"]


def test_without_description_marks_missing():
    assert one("30 roxinho").missing == ["description"]


def test_filler_words_and_brl_forms():
    assert one("R$ 1.234,56 de gasolina no cartão azul em 2x").amount_cents == 123456
    assert one("gasolina no cartão azul em 2x R$ 1.234,56").description == "gasolina"
    assert one("20 reais lanche").amount_cents == 2000


def test_two_lines_and_semicolon():
    drafts = parse_simple("120 mercado roxinho 3x\n15 pão débito", ALIASES, TODAY)
    assert [d.amount_cents for d in drafts] == [12000, 1500]
    drafts = parse_simple("10 café; 5 bala", ALIASES, TODAY)
    assert [d.description for d in drafts] == ["café", "bala"]


def test_day_and_numeric_date():
    assert one("40 cinema dia 10").purchase_date == date(2026, 11, 10)
    assert one("40 cinema 3/10").purchase_date == date(2026, 10, 3)


def test_parcel_in_progress_returns_none():
    assert parse_simple("100 geladeira parcela 3/10 roxinho", ALIASES, TODAY) is None
    assert parse_simple("100 sofá parcela 1/1", ALIASES, TODAY) is None


def test_slash_without_parcel_word_is_only_a_date():
    assert one("100 sofá 3/10").purchase_date == date(2026, 10, 3)
    assert one("100 sofá 3/10").installments == 1
    assert parse_simple("100 sofá 3/15", ALIASES, TODAY) is None


def test_no_amount_returns_none():
    assert parse_simple("comprei pão", ALIASES, TODAY) is None
    assert parse_simple("", ALIASES, TODAY) is None


def test_two_amounts_is_ambiguous():
    assert parse_simple("10 pão 20 leite", ALIASES, TODAY) is None


def test_one_bad_line_makes_everything_none():
    assert parse_simple("10 pão\ncomprei algo", ALIASES, TODAY) is None


def test_invalid_date_returns_none():
    assert parse_simple("10 pão 31/02", ALIASES, TODAY) is None


def test_ambiguous_card_marks_missing():
    aliases = {"azul": "card-a", "roxo": "card-b"}
    drafts = parse_simple("10 pão azul roxo", aliases, TODAY)
    assert drafts[0].card_id is None
