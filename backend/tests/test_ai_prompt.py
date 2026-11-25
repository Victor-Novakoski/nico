import json
from datetime import date

import pytest
from pydantic import ValidationError

from nico.ai.prompt import ExtractionContext, extraction_schema, parse_extraction, system_prompt
from nico.ai.schema import Method, Person

CTX = ExtractionContext(
    today=date(2026, 3, 5),
    methods=[Method("m1", ["Cartão Azul", "azul"], "credito"), Method("m2", ["pix"], "pix")],
    people=[Person("p1", ["Fulana", "Fu"]), Person("p2", ["Beltrano"])],
)


def test_prompt_has_date_and_closed_lists():
    text = system_prompt(CTX)
    assert "quinta, 05/03/2026" in text
    assert "Cartão Azul, azul (credito)" in text
    assert "pix (pix)" in text
    assert "Fulana, Fu" in text and "Beltrano" in text


def test_prompt_with_empty_lists():
    text = system_prompt(ExtractionContext(today=date(2026, 3, 8)))
    assert "domingo, 08/03/2026" in text
    assert "- nenhum" in text and "- nenhuma" in text


def test_schema_has_no_refs():
    schema = extraction_schema()
    dumped = json.dumps(schema)
    assert "$ref" not in dumped and "$defs" not in dumped
    item = schema["properties"]["items"]["items"]
    assert item["type"] == "object"
    assert "amount_text" in item["properties"]


def test_parse_good_and_bad():
    ok = parse_extraction('{"items": [{"description": "pão", "amount_text": "15"}]}')
    assert ok.items[0].amount_text == "15"
    with pytest.raises(ValidationError):
        parse_extraction("isto não é json")
    with pytest.raises(ValidationError):
        parse_extraction('{"items": "nao e lista"}')
