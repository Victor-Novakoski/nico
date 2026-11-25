from datetime import date
from pathlib import Path

import pytest

from nico import evals
from nico.ai.base import ProviderUnavailable
from nico.ai.schema import ExtractedItem, Extraction
from nico.eval_cases import EvalCase, EvalMethod, EvalPerson, ExpectedDraft
from nico.evals import PredictedDraft, compare, format_report, summarize

TODAY = date(2026, 11, 25)
SECRET_TEXT = "zzgasto-inventado-xyzzy 77 na loja plugh"


def make_case(case_id="k1", text=SECRET_TEXT, n=1) -> EvalCase:
    return EvalCase(
        id=case_id,
        text=text,
        today=TODAY,
        methods=[EvalMethod(id="azul", aliases=["azul"], type="credito")],
        people=[EvalPerson(id="fulana", names=["Fulana"])],
        expected=[
            ExpectedDraft(
                description="mercado",
                amount_cents=1000 * (i + 1),
                method_id="azul",
                purchase_date=TODAY,
                installments=1,
                person_id=None,
            )
            for i in range(n)
        ],
    )


def good(i=0, **over) -> PredictedDraft:
    base = dict(
        description="compras no mercado",
        amount_cents=1000 * (i + 1),
        method_id="azul",
        purchase_date=TODAY,
        installments=1,
        person_id=None,
    )
    base.update(over)
    return PredictedDraft(**base)


def test_compare_all_right():
    r = compare(make_case(), [good()])
    assert r.exact and r.failed_fields == [] and not r.count_mismatch
    assert all(r.correct[f] == r.total[f] == 1 for f in evals.FIELDS)


def test_compare_one_field_wrong():
    r = compare(make_case(), [good(amount_cents=999)])
    assert r.failed_fields == ["amount_cents"]
    assert not r.exact
    assert r.correct["amount_cents"] == 0 and r.correct["method_id"] == 1


def test_wrong_description_does_not_break_exact():
    r = compare(make_case(), [good(description="outra coisa")])
    assert r.failed_fields == ["description"]
    assert r.exact


def test_compare_wrong_count_and_empty():
    r = compare(make_case(n=2), [good()])
    assert r.count_mismatch and not r.exact
    assert r.total["amount_cents"] == 2 and r.correct["amount_cents"] == 1
    extra = compare(make_case(), [good(), good(1)])
    assert extra.count_mismatch and not extra.exact
    empty = compare(make_case(), [])
    assert empty.correct["amount_cents"] == 0 and empty.total["amount_cents"] == 1
    assert set(empty.failed_fields) == set(evals.FIELDS)


def test_fuzzy_description():
    assert evals._description_ok("pão", "Pao de queijo")
    assert evals._description_ok("mercado do bairro", "Mercado")
    assert not evals._description_ok("mercado", "farmácia")
    assert not evals._description_ok("mercado", None)
    assert evals._description_ok(None, "qualquer")


def test_summarize_percentages():
    results = [compare(make_case("a"), [good()]), compare(make_case("b"), [good(amount_cents=1)])]
    results[1].seconds = 0.2
    report = summarize(results)
    assert (report.correct["amount_cents"], report.total["amount_cents"]) == (1, 2)
    assert report.exact == 1 and report.cases == 2
    assert report.mean_seconds == pytest.approx(0.1)
    assert [r.case_id for r in report.failing] == ["b"]
    text = format_report(report, show_text=False)
    assert "amount_cents: 50.0% (1/2)" in text
    assert "method_id: 100.0% (2/2)" in text


def test_format_report_hides_text_unless_asked():
    results = [compare(make_case(), [good(amount_cents=1)], failure="ProviderUnavailable")]
    report = summarize(results)
    hidden = format_report(report, show_text=False)
    assert "zzgasto" not in hidden and "mercado" not in hidden
    assert "k1" in hidden and "amount_cents" in hidden and "ProviderUnavailable" in hidden
    assert SECRET_TEXT in format_report(report, show_text=True)


def test_rules_end_to_end_on_examples(capsys):
    assert evals.main(["--set", "examples", "--provider", "rules"]) == 0
    out = capsys.readouterr().out
    for name in evals.FIELDS:
        assert f"  {name}: " in out
    assert "Tempo médio por caso" in out
    line = next(ln for ln in out.splitlines() if ln.startswith("  amount_cents:"))
    assert not line.startswith("  amount_cents: 0.0%")


def test_limit(capsys):
    evals.main(["--set", "examples", "--limit", "3"])
    assert "3 casos" in capsys.readouterr().out


class FakeProvider:
    def __init__(self):
        self.calls = 0

    def extract(self, text, context):
        self.calls += 1
        if self.calls == 1:
            raise ProviderUnavailable("mensagem com texto secreto")
        return Extraction(items=[ExtractedItem(description="x", amount_text="10")])


def test_ai_provider_path_records_exception_type_only(monkeypatch, capsys):
    monkeypatch.setattr(evals, "provider_registry", lambda: {"groq": FakeProvider})
    evals.main(["--set", "examples", "--provider", "groq", "--limit", "2"])
    out = capsys.readouterr().out
    assert "falha=ProviderUnavailable" in out
    assert "texto secreto" not in out
    assert "Falhas (erro do provedor ou frase não entendida): 1" in out


def test_real_set_missing_file_exits_cleanly(monkeypatch, tmp_path: Path):
    monkeypatch.setattr(evals, "REPO_ROOT", tmp_path)
    with pytest.raises(SystemExit) as exc:
        evals.main(["--set", "real"])
    assert exc.value.code not in (0, None)
    assert str(tmp_path) not in str(exc.value.code)
    assert "evals/real/frases.jsonl" in str(exc.value.code)


def test_real_set_hides_text_even_when_failing(monkeypatch, tmp_path: Path, capsys):
    (tmp_path / "evals/real").mkdir(parents=True)
    src = Path(evals.__file__).parents[3] / "evals/examples/frases.jsonl"
    first = src.read_text(encoding="utf-8").splitlines()[0]
    (tmp_path / "evals/real/frases.jsonl").write_text(first + "\n", encoding="utf-8")
    monkeypatch.setattr(evals, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(evals, "provider_registry", lambda: {"groq": FakeProvider})
    evals.main(["--set", "real", "--provider", "groq"])
    out = capsys.readouterr().out
    assert "Mercado Bom Preço" not in out and "frase:" not in out
    assert "c01" in out
