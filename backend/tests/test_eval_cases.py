import json
import re
from pathlib import Path

import pytest

from nico.ai.prompt import ExtractionContext
from nico.eval_cases import EvalCase, load_cases, to_context
from nico.money import parse_brl

EXAMPLES = Path(__file__).parents[2] / "evals/examples/frases.jsonl"

REQUIRED_TAGS = {
    "virgula-decimal",
    "milhar",
    "parcelas",
    "ontem",
    "dia-n",
    "data-numerica",
    "dois-gastos",
    "dois-meios",
    "pessoa",
    "metade",
    "sem-meio",
    "sem-valor",
    "pix",
    "debito",
    "dinheiro",
    "parcelas-a-vista",
    "r-cifrao",
    "reais",
    "voz",
}

_AMOUNT_RE = re.compile(r"(?:R\$\s*)?\d[\d.]*(?:,\d+)?(?:\s*reais)?")


@pytest.fixture(scope="module")
def cases() -> list[EvalCase]:
    return load_cases(EXAMPLES)


def test_has_thirty_cases_with_unique_ids(cases):
    assert len(cases) == 30
    assert len({c.id for c in cases}) == 30


def test_expected_ids_exist_in_closed_lists(cases):
    for case in cases:
        method_ids = {m.id for m in case.methods}
        person_ids = {p.id for p in case.people}
        assert case.expected, case.id
        for draft in case.expected:
            assert draft.method_id is None or draft.method_id in method_ids, case.id
            assert draft.person_id is None or draft.person_id in person_ids, case.id


def test_required_tags_are_covered(cases):
    used = {t for c in cases for t in c.tags}
    assert REQUIRED_TAGS - used == set()


def test_to_context(cases):
    for case in cases:
        ctx = to_context(case)
        assert isinstance(ctx, ExtractionContext)
        assert ctx.today == case.today
        assert [m.id for m in ctx.methods] == [m.id for m in case.methods]
        assert [p.id for p in ctx.people] == [p.id for p in case.people]


def test_expected_amounts_appear_in_text(cases):
    for case in cases:
        found = set()
        for match in _AMOUNT_RE.finditer(case.text):
            try:
                found.add(parse_brl(match.group()))
            except ValueError:
                continue
        for draft in case.expected:
            if draft.amount_cents is not None:
                assert draft.amount_cents in found, case.id


def _line(**overrides) -> str:
    base = {"id": "x", "text": "10 de pão", "today": "2026-11-25", "methods": [], "people": []}
    base["expected"] = [{"description": "pão", "amount_cents": 1000}]
    base.update(overrides)
    return json.dumps(base)


def test_load_cases_ignores_blank_lines(tmp_path):
    path = tmp_path / "c.jsonl"
    path.write_text(f"\n{_line()}\n\n   \n{_line(id='y')}\n", encoding="utf-8")
    cases = load_cases(path)
    assert [c.id for c in cases] == ["x", "y"]
    assert cases[0].expected[0].installments == 1


def test_load_cases_bad_json_mentions_line(tmp_path):
    path = tmp_path / "c.jsonl"
    path.write_text(f"{_line()}\n{{nao e json\n", encoding="utf-8")
    with pytest.raises(ValueError, match=r":2:"):
        load_cases(path)


def test_load_cases_extra_field_is_error(tmp_path):
    path = tmp_path / "c.jsonl"
    path.write_text(_line(surprise=1) + "\n", encoding="utf-8")
    with pytest.raises(ValueError, match=r":1:"):
        load_cases(path)


def test_load_cases_extra_field_in_expected_is_error(tmp_path):
    path = tmp_path / "c.jsonl"
    path.write_text(_line(expected=[{"amount": 1}]) + "\n", encoding="utf-8")
    with pytest.raises(ValueError, match=r":1:"):
        load_cases(path)
