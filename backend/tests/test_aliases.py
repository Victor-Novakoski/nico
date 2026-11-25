from nico.aliases import match_card, normalize

ALIASES = {
    "roxinho": "card-a",
    "cartao azul": "card-b",
    "debito": "card-c",
    "inter": "card-d",
}


def test_normalize_lowercase_accents_spaces_and_edges():
    assert normalize("  Débito,  DA   Conta! ") == "debito, da conta"


def test_match_accent_insensitive():
    assert match_card("15 de pão no débito", ALIASES) == "card-c"
    assert match_card("15 de pao no debito", {"débito": "card-c"}) == "card-c"


def test_match_case_insensitive():
    assert match_card("120 no ROXINHO", ALIASES) == "card-a"


def test_match_multiword_alias():
    assert match_card("50 de gasolina no Cartão   Azul em 3x", ALIASES) == "card-b"


def test_match_with_punctuation_around_alias():
    assert match_card("mercado, roxinho. pronto", ALIASES) == "card-a"


def test_word_boundary_does_not_match_inside_word():
    assert match_card("assinei a internet", ALIASES) is None
    assert match_card("30 no inter", ALIASES) == "card-d"


def test_longest_alias_wins():
    aliases = {"azul": "card-a", "cartao azul": "card-b"}
    assert match_card("compra no cartão azul", aliases) == "card-b"


def test_tie_between_different_cards_is_ambiguous():
    aliases = {"roxinho": "card-a", "azulzao": "card-b"}
    assert match_card("roxinho e azulzao", aliases) is None


def test_several_aliases_of_same_card_are_not_ambiguous():
    aliases = {"roxinho": "card-a", "azulzao": "card-a"}
    assert match_card("roxinho e azulzao", aliases) == "card-a"


def test_no_match_returns_none():
    assert match_card("15 de pão", ALIASES) is None
    assert match_card("", ALIASES) is None
    assert match_card("qualquer coisa", {}) is None


def test_empty_alias_is_ignored():
    assert match_card("qualquer coisa", {"": "card-a", "  ": "card-b"}) is None
