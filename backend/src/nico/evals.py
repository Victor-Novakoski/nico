"""Roda os evals e mede o acerto por campo (decisões 002, 005 e 007).

    python -m nico.evals --set examples|real [--provider rules|ollama|groq|...] [--limit N]

`compare`, `summarize` e `format_report` são puras (sem rede, sem relógio). Com
`--set real` o relatório nunca imprime o texto das frases nem descrições: só ids de
casos, nomes de campos e o nome do tipo da exceção (nunca a mensagem).
"""

from __future__ import annotations

import argparse
import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

from nico import rules
from nico.ai import schema
from nico.ai.registry import provider_registry
from nico.aliases import normalize
from nico.eval_cases import EvalCase, ExpectedDraft, load_cases, to_context

REPO_ROOT = Path(__file__).parents[3]
SETS = {"examples": "evals/examples/frases.jsonl", "real": "evals/real/frases.jsonl"}
PROVIDERS = ["rules", "ollama", "groq", "cloudflare", "openrouter"]

# Campos comparados, na ordem do relatório. `description` é aproximado.
FIELDS = (
    "amount_cents",
    "method_id",
    "purchase_date",
    "installments",
    "person_id",
    "description",
)
EXACT_FIELDS = tuple(f for f in FIELDS if f != "description")


@dataclass
class PredictedDraft:
    """O que o provedor produziu, com os mesmos campos de `ExpectedDraft`."""

    description: str | None = None
    amount_cents: int | None = None
    method_id: str | None = None
    purchase_date: date | None = None
    installments: int = 1
    person_id: str | None = None


class NotUnderstood(Exception):
    """As regras não entenderam a frase (conta como falha)."""


@dataclass
class CaseResult:
    case_id: str
    text: str
    expected_count: int
    predicted_count: int
    correct: dict[str, int] = field(default_factory=dict)  # campo -> acertos
    total: dict[str, int] = field(default_factory=dict)  # campo -> esperados
    failed_fields: list[str] = field(default_factory=list)
    failure: str | None = None  # nome do tipo da exceção ou "NotUnderstood"
    seconds: float = 0.0

    @property
    def count_mismatch(self) -> bool:
        return self.expected_count != self.predicted_count

    @property
    def exact(self) -> bool:
        """Mesmo número de rascunhos e todos os campos (menos descrição) certos."""
        return (
            self.failure is None
            and not self.count_mismatch
            and not any(f in EXACT_FIELDS for f in self.failed_fields)
        )


@dataclass
class Report:
    cases: int
    correct: dict[str, int]
    total: dict[str, int]
    exact: int
    count_mismatches: int
    failures: int
    mean_seconds: float
    failing: list[CaseResult]  # casos com alguma falha de campo, contagem ou exceção


def _description_ok(expected: str | None, predicted: str | None) -> bool:
    """Sem dica esperada, nada a conferir; senão, uma contém a outra (normalizadas)."""
    hint = normalize(expected or "")
    if not hint:
        return True
    got = normalize(predicted or "")
    return bool(got) and (hint in got or got in hint)


def _field_ok(name: str, expected: ExpectedDraft, predicted: PredictedDraft) -> bool:
    if name == "description":
        return _description_ok(expected.description, predicted.description)
    return getattr(expected, name) == getattr(predicted, name)


def compare(
    case: EvalCase,
    predicted: Sequence[PredictedDraft],
    *,
    failure: str | None = None,
    seconds: float = 0.0,
) -> CaseResult:
    """Compara por índice: o i-ésimo esperado contra o i-ésimo previsto.

    Esperado sem previsto correspondente erra todos os campos; previsto a mais não
    entra nos campos, só no `count_mismatch`.
    """
    expected = case.expected
    result = CaseResult(
        case_id=case.id,
        text=case.text,
        expected_count=len(expected),
        predicted_count=len(predicted),
        correct=dict.fromkeys(FIELDS, 0),
        total=dict.fromkeys(FIELDS, 0),
        failure=failure,
        seconds=seconds,
    )
    failed: set[str] = set()
    for index, want in enumerate(expected):
        got = predicted[index] if index < len(predicted) else None
        for name in FIELDS:
            result.total[name] += 1
            if got is not None and _field_ok(name, want, got):
                result.correct[name] += 1
            else:
                failed.add(name)
    result.failed_fields = [f for f in FIELDS if f in failed]
    return result


def summarize(results: Sequence[CaseResult]) -> Report:
    correct = dict.fromkeys(FIELDS, 0)
    total = dict.fromkeys(FIELDS, 0)
    for r in results:
        for name in FIELDS:
            correct[name] += r.correct.get(name, 0)
            total[name] += r.total.get(name, 0)
    count = len(results)
    return Report(
        cases=count,
        correct=correct,
        total=total,
        exact=sum(1 for r in results if r.exact),
        count_mismatches=sum(1 for r in results if r.count_mismatch),
        failures=sum(1 for r in results if r.failure is not None),
        mean_seconds=(sum(r.seconds for r in results) / count) if count else 0.0,
        failing=[r for r in results if r.failure or r.count_mismatch or r.failed_fields],
    )


def _pct(correct: int, total: int) -> str:
    return f"{100 * correct / total:.1f}%" if total else "n/a"


def format_report(report: Report, show_text: bool, title: str = "") -> str:
    """Relatório em texto. Com `show_text` falso, nunca inclui frases nem descrições."""
    lines = [f"Evals{f' ({title})' if title else ''}: {report.cases} casos"]
    lines.append("Acerto por campo:")
    for name in FIELDS:
        c, t = report.correct[name], report.total[name]
        lines.append(f"  {name}: {_pct(c, t)} ({c}/{t})")
    lines.append(
        f"Acerto exato (todos os campos menos descrição): {_pct(report.exact, report.cases)}"
        f" ({report.exact}/{report.cases})"
    )
    lines.append(f"Casos com número de rascunhos errado: {report.count_mismatches}")
    lines.append(f"Falhas (erro do provedor ou frase não entendida): {report.failures}")
    lines.append(f"Tempo médio por caso: {report.mean_seconds * 1000:.1f} ms")
    if report.failing:
        lines.append("Casos com problema:")
        for r in report.failing:
            parts = []
            if r.failure:
                parts.append(f"falha={r.failure}")
            if r.count_mismatch:
                parts.append(f"rascunhos={r.predicted_count}/{r.expected_count}")
            if r.failed_fields:
                parts.append("campos=" + ",".join(r.failed_fields))
            lines.append(f"  {r.case_id}: {'; '.join(parts)}")
            if show_text:
                lines.append(f"    frase: {r.text}")
    return "\n".join(lines)


Predictor = Callable[[EvalCase], list[PredictedDraft]]


CASH_TYPES = {"debito", "pix", "dinheiro"}


def rules_predictor(case: EvalCase) -> list[PredictedDraft]:
    """O mesmo que a rota de rascunhos faz sem IA, inclusive a regra da decisão 010."""
    aliases = {a: m.id for m in case.methods for a in m.aliases}
    types = {m.id: m.type for m in case.methods}
    drafts = rules.parse_simple(case.text, aliases, case.today)
    if drafts is None:
        raise NotUnderstood
    return [
        PredictedDraft(
            description=d.description,
            amount_cents=d.amount_cents,
            method_id=d.card_id,
            purchase_date=d.purchase_date,
            # Meio à vista não parcela: "3x" no Pix fica 1 (decisão 010).
            installments=1 if types.get(d.card_id) in CASH_TYPES else d.installments,
            person_id=None,
        )
        for d in drafts
    ]


def ai_predictor(provider: object) -> Predictor:
    def predict(case: EvalCase) -> list[PredictedDraft]:
        context = to_context(case)
        extraction = provider.extract(case.text, context)  # type: ignore[attr-defined]
        drafts = schema.validate(extraction, context.methods, context.people, case.today)
        return [
            PredictedDraft(
                description=d.description,
                amount_cents=d.amount_cents,
                method_id=d.method_id,
                purchase_date=d.purchase_date,
                installments=d.installments,
                person_id=d.person_id,
            )
            for d in drafts
        ]

    return predict


def run_cases(cases: Sequence[EvalCase], predict: Predictor) -> list[CaseResult]:
    results = []
    for case in cases:
        start = time.perf_counter()
        failure = None
        predicted: list[PredictedDraft] = []
        try:
            predicted = predict(case)
        except Exception as exc:  # só o nome do tipo: a mensagem pode ter texto da frase
            failure = type(exc).__name__
        results.append(
            compare(case, predicted, failure=failure, seconds=time.perf_counter() - start)
        )
    return results


def _build_predictor(name: str) -> Predictor:
    if name == "rules":
        return rules_predictor
    try:
        return ai_predictor(provider_registry()[name]())
    except Exception as exc:
        raise SystemExit(
            f"Não foi possível preparar o provedor '{name}' ({type(exc).__name__}). "
            "Confira as variáveis de ambiente dele."
        ) from None


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="nico.evals", description="Mede o acerto por campo.")
    parser.add_argument("--set", dest="set_name", choices=sorted(SETS), required=True)
    parser.add_argument("--provider", choices=PROVIDERS, default="rules")
    parser.add_argument("--limit", type=int, default=None)
    args = parser.parse_args(argv)

    relative = SETS[args.set_name]
    path = REPO_ROOT / relative
    if not path.is_file():
        raise SystemExit(f"Arquivo de casos não encontrado: {relative}")
    is_real = args.set_name == "real"
    try:
        cases = load_cases(path)
    except ValueError as exc:
        # Em `real`, a mensagem do leitor pode citar o conteúdo da linha: não repete.
        detail = "veja o formato em evals/README.md" if is_real else str(exc)
        raise SystemExit(f"Casos inválidos em {relative}: {detail}") from None
    if args.limit is not None:
        cases = cases[: max(args.limit, 0)]
    if not cases:
        raise SystemExit(f"Nenhum caso em {relative}")

    results = run_cases(cases, _build_predictor(args.provider))
    title = f"{args.set_name}, provedor {args.provider}"
    print(format_report(summarize(results), show_text=not is_real, title=title))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
