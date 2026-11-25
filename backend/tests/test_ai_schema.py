from datetime import date

from nico.ai.schema import ExtractedItem, Extraction, Method, Person, validate

TODAY = date(2026, 11, 25)
METHODS = [
    Method("m1", ["roxinho", "cartao roxo"], "credito"),
    Method("m2", ["debito", "conta azul"], "debito"),
    Method("m3", ["pix"], "pix"),
]
PEOPLE = [Person("p1", ["Ana"]), Person("p2", ["Beto", "Beto Souza"])]


def one(**kwargs):
    return validate(Extraction(items=[ExtractedItem(**kwargs)]), METHODS, PEOPLE, TODAY)[0]


def test_valid_item():
    d = one(
        description="mercado",
        amount_text="R$ 1.234,56",
        method="no roxinho",
        installments=3,
        date_text="ontem",
        person="Ana",
    )
    assert d.amount_cents == 123456
    assert (d.method_id, d.method_type) == ("m1", "credito")
    assert d.purchase_date == date(2026, 11, 24)
    assert d.installments == 3
    assert d.person_id == "p1"
    assert d.missing == []
    assert d.sources["amount"] == "ia"
    assert d.sources["method_id"] == "ia"


def test_amount_that_does_not_read_is_missing():
    for text in ("doze e cinquenta", "1,234.56", "0", "", None):
        d = one(description="pao", amount_text=text, method="pix", person="Ana")
        assert d.amount_cents is None
        assert "amount" in d.missing


def test_unknown_method_is_empty_and_missing():
    d = one(description="pao", amount_text="15", method="cartao verde", person="Ana")
    assert d.method_id is None and d.method_type is None
    assert "method_id" in d.missing


def test_no_method_is_empty_and_missing():
    d = one(description="pao", amount_text="15", person="Ana")
    assert d.method_id is None
    assert "method_id" in d.missing


def test_debit_with_three_installments_becomes_one():
    d = one(description="tenis", amount_text="300", method="debito", installments=3, person="Ana")
    assert d.installments == 1
    assert "installments" in d.missing
    assert d.method_id == "m2"


def test_credit_keeps_installments_and_cash_one_is_fine():
    assert one(amount_text="300", method="roxinho", installments=3).installments == 3
    d = one(amount_text="30", method="pix", installments=1)
    assert d.installments == 1 and "installments" not in d.missing


def test_unknown_person_is_empty_and_missing():
    d = one(description="pao", amount_text="15", method="pix", person="Zeca")
    assert d.person_id is None
    assert "person_id" in d.missing


def test_invalid_date_is_missing_and_absent_date_is_today():
    bad = one(amount_text="15", date_text="31/02")
    assert bad.purchase_date is None and "purchase_date" in bad.missing
    none = one(amount_text="15")
    assert none.purchase_date == TODAY
    assert none.sources["purchase_date"] == "padrao"


def test_empty_list():
    assert validate(Extraction(items=[]), METHODS, PEOPLE, TODAY) == []


def test_json_schema_has_list_of_items():
    schema = Extraction.model_json_schema()
    assert schema["properties"]["items"]["type"] == "array"
    item = schema["$defs"]["ExtractedItem"]["properties"]
    assert {"description", "amount_text", "method", "installments", "date_text", "person"} <= set(
        item
    )
