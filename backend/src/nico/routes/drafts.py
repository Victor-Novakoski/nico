"""Rascunhos a partir de uma frase: regras primeiro, IA depois (decisões 006 e 007).

Não grava nada. As regras tentam sozinhas; só se não entenderem e a pessoa tiver a IA
ligada a cascata é chamada (nunca para frase que as regras resolvem). Sem IA, ou se
todos os provedores falharem, volta `fallback: "form"` para a tela abrir o formulário.
A IA só extrai trechos: valor, data, parcelas, meio e pessoa saem de `ai.schema.validate`.
"""

import logging
import re
import unicodedata
from typing import Annotated, Literal

import psycopg
from fastapi import APIRouter, Depends, HTTPException, UploadFile
from pydantic import BaseModel, StringConstraints

from nico import config, dates, rules, scope
from nico.ai.audio import MAX_AUDIO_BYTES, AudioRejected, check_audio
from nico.ai.base import AllProvidersFailed, ProviderConfigError
from nico.ai.cascade import Cascade, build_cascade
from nico.ai.prompt import ExtractionContext
from nico.ai.registry import provider_registry
from nico.ai.schema import AiDraft, Method, Person, validate
from nico.aliases import normalize
from nico.auth import CurrentUser, current_user
from nico.db import get_conn
from nico.money import parse_brl

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/drafts")


def get_cascade() -> Cascade | None:
    """Cascata de `AI_PROVIDERS`; `None` se vazia ou mal configurada (cai no formulário)."""
    names = config.optional("AI_PROVIDERS", "")
    if not names.strip():
        return None
    try:
        return build_cascade(names, provider_registry())
    except (ValueError, RuntimeError):
        logger.warning("AI_PROVIDERS inválido ou provedor sem configuração")
        return None


Conn = Annotated[psycopg.Connection, Depends(get_conn)]
User = Annotated[CurrentUser, Depends(current_user)]
Ai = Annotated[Cascade | None, Depends(get_cascade)]
Text = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=500)]
Kind = Literal["credito", "debito", "pix", "dinheiro"]
CASH_KINDS = {"debito", "pix", "dinheiro"}

_INSTALLMENT_RE = re.compile(r"\b\d{1,2}\s*x\b", re.IGNORECASE)
_MONEY_TOKEN_RE = re.compile(r"(?:r\$\s*)?\d[\d.]*(?:,\d+)?", re.IGNORECASE)


class ParseIn(BaseModel):
    text: Text


class SpanOut(BaseModel):
    """Trecho da frase original que virou um campo: posições em caracteres, `end` exclusivo."""

    field: str
    start: int
    end: int


class DraftOut(BaseModel):
    description: str
    amount_cents: int
    method_id: str | None
    method_type: Kind | None
    person_id: str
    purchase_date: str
    installments: int
    missing: list[str]
    # Campo -> "frase" (veio do texto) ou "padrao" (as regras assumiram o valor).
    # Campo sem valor (descrição vazia, meio não reconhecido, sem principal) não aparece.
    sources: dict[str, str]
    # Onde na frase cada campo apareceu. Campo do padrão ou não achado fica sem trecho.
    spans: list[SpanOut] = []


class ParseOut(BaseModel):
    understood: bool
    drafts: list[DraftOut]
    # "rules" ou o nome do provedor que respondeu; None quando ninguém entendeu.
    origin: str | None = None
    # "form": a tela abre o formulário manual. Campos duvidosos de cada rascunho: `missing`.
    fallback: Literal["form"] | None = None


class AudioOut(ParseOut):
    # O que foi entendido do áudio, para a pessoa conferir; None se ninguém transcreveu.
    transcript: str | None = None


def _load_aliases(
    conn: psycopg.Connection, person_id: str
) -> tuple[dict[str, str], dict[str, str]]:
    """({apelido: id do meio}, {id do meio: tipo}).

    Além dos apelidos cadastrados, o próprio nome de cada meio vale como apelido
    (normalizado). Apelido cadastrado vence nome; nome repetido entre meios fica
    com o primeiro (os apelidos são únicos no banco, os nomes não).
    Só os meios de que a pessoa é dona (decisão 013): compra só entra com meio
    próprio, então apelido de meio alheio nem é reconhecido.
    """
    kinds: dict[str, str] = {}
    names: dict[str, str] = {}
    for method_id, name, kind in conn.execute(
        "select id::text, name, kind from payment_method"
        " where owner_person_id = %s order by name, id",
        (person_id,),
    ):
        kinds[method_id] = kind
        names.setdefault(normalize(name), method_id)
    aliases: dict[str, str] = {}
    for alias, method_id in conn.execute(
        "select a.alias, a.payment_method_id::text from payment_method_alias a"
        " join payment_method pm on pm.id = a.payment_method_id"
        " where pm.owner_person_id = %s",
        (person_id,),
    ):
        aliases[normalize(alias)] = method_id
    for name, method_id in names.items():
        if name:
            aliases.setdefault(name, method_id)
    return aliases, kinds


def _segments(text: str) -> list[str]:
    # Mesma divisão de rules.parse_simple, para casar segmento e rascunho.
    return [s.strip() for s in re.split(r"[\n;]", text) if s.strip()]


def _fold(text: str) -> str:
    """Minúsculas e sem acento, mantendo o tamanho (posições valem no texto original)."""
    out = []
    for char in text:
        base = unicodedata.normalize("NFD", char)[0].lower()
        out.append(base if len(base) == 1 else char)
    return "".join(out)


def _find_alias(segment: str, aliases: dict[str, str], method_id: str) -> tuple[int, int] | None:
    folded = _fold(segment)
    candidates = sorted((a for a, m in aliases.items() if m == method_id and a), key=len)
    for alias in reversed(candidates):  # o mais longo primeiro
        words = r"\s+".join(re.escape(w) for w in _fold(alias).split())
        found = re.search(rf"(?<!\w){words}(?!\w)", folded)
        if found:
            return found.span()
    return None


def _find_amount(segment: str, amount_cents: int) -> tuple[int, int] | None:
    for found in _MONEY_TOKEN_RE.finditer(segment):
        try:
            if parse_brl(found.group()) == amount_cents:
                return found.span()
        except ValueError:
            continue
    return None


def _find_spans(
    segment: str,
    offset: int,
    draft: DraftOut,
    aliases: dict[str, str],
) -> list[SpanOut]:
    """Procura no segmento (que começa em `offset` da frase) o texto de cada campo.

    Só campos que vieram da frase; o que não for achado fica sem trecho.
    """
    found: dict[str, tuple[int, int] | None] = {}
    sources = draft.sources
    if sources.get("amount_cents") not in (None, "padrao"):
        found["amount_cents"] = _find_amount(segment, draft.amount_cents)
    if sources.get("description") not in (None, "padrao") and draft.description:
        start = _fold(segment).find(_fold(draft.description))
        found["description"] = (start, start + len(draft.description)) if start >= 0 else None
    if sources.get("method_id") not in (None, "padrao") and draft.method_id:
        found["method_id"] = _find_alias(segment, aliases, draft.method_id)
    if sources.get("installments") not in (None, "padrao") and draft.installments > 1:
        match = _INSTALLMENT_RE.search(segment)
        found["installments"] = match.span() if match else None
    return [
        SpanOut(field=f, start=offset + a, end=offset + b)
        for f, p in found.items()
        if p
        for a, b in [p]
    ]


def _date_in_text(segment: str, today) -> bool:
    try:
        return dates.parse_date_pt(segment, today) is not None
    except ValueError:
        return False


@router.post("/parse")
def parse_drafts(body: ParseIn, conn: Conn, user: User, cascade: Ai) -> ParseOut:
    return _parse_text(body.text, conn, user, cascade)


@router.post("/audio")
def parse_audio(file: UploadFile, conn: Conn, user: User, cascade: Ai) -> AudioOut:
    """Áudio, transcrição pela cascata, mesmo caminho de `/parse`. Nada é guardado nem logado."""
    audio = file.file.read(MAX_AUDIO_BYTES + 1)
    try:
        mime = check_audio(audio, file.content_type or "")
    except AudioRejected as error:
        too_big = len(audio) > MAX_AUDIO_BYTES
        messages = {
            "formato de áudio não aceito": "Formato de áudio não aceito.",
            "áudio vazio": "O áudio veio vazio.",
        }
        message = (
            "O áudio passa de 4 MB." if too_big else messages.get(str(error), "Áudio inválido.")
        )
        status = 413 if too_big else 422
        raise HTTPException(status_code=status, detail=message) from error
    row = conn.execute("select ai_enabled from app_user where id = %s", (user.id,)).fetchone()
    if not (row and row[0]) or cascade is None:
        return AudioOut(understood=False, drafts=[], fallback="form")
    try:
        _, transcript = cascade.transcribe(audio, mime)
    except AllProvidersFailed:
        return AudioOut(understood=False, drafts=[], fallback="form")
    except ProviderConfigError:
        logger.error("provedor de IA com configuração inválida")
        return AudioOut(understood=False, drafts=[], fallback="form")
    transcript = transcript.strip()[:500]
    result = _parse_text(transcript, conn, user, cascade)
    return AudioOut(**result.model_dump(), transcript=transcript)


def _parse_text(
    text: str, conn: psycopg.Connection, user: CurrentUser, cascade: Cascade | None
) -> ParseOut:
    aliases, kinds = _load_aliases(conn, user.person_id)
    row = conn.execute(
        "select default_method_id::text, ai_enabled from app_user where id = %s", (user.id,)
    ).fetchone()
    default_method_id = row[0] if row else None
    ai_enabled = bool(row[1]) if row else False
    today = dates.today_sp()
    parsed = rules.parse_simple(text, aliases, today)
    if parsed is None:
        if ai_enabled and cascade is not None:
            return _parse_with_ai(
                text, cascade, conn, aliases, kinds, default_method_id, user, today
            )
        return ParseOut(understood=False, drafts=[], fallback="form")
    segments = _segments(text)
    drafts = []
    cursor = 0
    for draft, segment in zip(parsed, segments, strict=True):
        offset = text.find(segment, cursor)
        cursor = offset + len(segment)
        method_id = draft.card_id
        from_default = False
        if method_id is None and default_method_id in kinds:
            method_id = default_method_id
            from_default = True
        kind = kinds.get(method_id) if method_id else None
        installments = draft.installments
        missing = list(draft.missing)
        if "card_id" in missing:
            if from_default:
                missing.remove("card_id")
            else:
                missing[missing.index("card_id")] = "method_id"
        # Decisão 010: meio à vista não parcela; "Nx" na frase fica como dúvida.
        if kind in CASH_KINDS and installments > 1:
            installments = 1
            missing.append("installments")
        sources = {"amount_cents": "frase"}
        if draft.description:
            sources["description"] = "frase"
        if method_id:
            sources["method_id"] = "padrao" if from_default else "frase"
        sources["person_id"] = "padrao"
        sources["purchase_date"] = "frase" if _date_in_text(segment, today) else "padrao"
        has_times = bool(_INSTALLMENT_RE.search(segment))
        sources["installments"] = "frase" if has_times and installments > 1 else "padrao"
        out = DraftOut(
            description=draft.description,
            amount_cents=draft.amount_cents,
            method_id=method_id,
            method_type=kind,
            person_id=user.person_id,
            purchase_date=draft.purchase_date.isoformat(),
            installments=installments,
            missing=missing,
            sources=sources,
        )
        out.spans = _find_spans(segment, offset, out, aliases)
        drafts.append(out)
    return ParseOut(understood=True, drafts=drafts, origin="rules")


def _parse_with_ai(
    text: str,
    cascade: Cascade,
    conn: psycopg.Connection,
    aliases: dict[str, str],
    kinds: dict[str, str],
    default_method_id: str | None,
    user: CurrentUser,
    today,
) -> ParseOut:
    failed = ParseOut(understood=False, drafts=[], fallback="form")
    by_method: dict[str, list[str]] = {}
    for alias, method_id in aliases.items():
        by_method.setdefault(method_id, []).append(alias)
    methods = [Method(mid, by_method.get(mid, []), kind) for mid, kind in kinds.items()]
    # Só a própria pessoa e quem divide grupo com ela (decisão 013).
    visible = list(scope.visible_people(conn, user.person_id))
    people = [
        Person(str(pid), [name])
        for pid, name in conn.execute("select id, name from person where id = any(%s)", (visible,))
    ]
    context = ExtractionContext(today=today, methods=methods, people=people)
    try:
        origin, extraction = cascade.extract(text, context)
    except AllProvidersFailed:
        return failed
    except ProviderConfigError:
        logger.error("provedor de IA com configuração inválida")
        return failed
    ai_drafts = validate(extraction, methods, people, today)
    if not ai_drafts:
        return failed
    drafts = [_ai_draft_out(d, kinds, default_method_id, user) for d in ai_drafts]
    for out in drafts:
        out.spans = _find_spans(text, 0, out, aliases)
    return ParseOut(understood=True, drafts=drafts, origin=origin)


def _ai_draft_out(
    draft: AiDraft, kinds: dict[str, str], default_method_id: str | None, user: CurrentUser
) -> DraftOut:
    missing = [{"amount": "amount_cents"}.get(m, m) for m in draft.missing]
    sources = {
        {"amount": "amount_cents"}.get(k, k): v
        for k, v in draft.sources.items()
        if k != "method_type"
    }
    method_id = draft.method_id
    if method_id is None and default_method_id in kinds:
        # Decisões 009/010: sem meio na frase, entra o principal, marcado como padrão.
        method_id = default_method_id
        missing = [m for m in missing if m != "method_id"]
        sources["method_id"] = "padrao"
    kind = kinds.get(method_id) if method_id else None
    installments = draft.installments
    if kind in CASH_KINDS and installments > 1:
        installments = 1
        missing.append("installments")
    person_id = draft.person_id
    if person_id is None:
        person_id = user.person_id
        missing = [m for m in missing if m != "person_id"]
        sources["person_id"] = "padrao"
    for field, value in (
        ("description", draft.description),
        ("amount_cents", draft.amount_cents),
        ("method_id", method_id),
        ("purchase_date", draft.purchase_date),
    ):
        if value is None:
            sources.pop(field, None)
    return DraftOut(
        description=draft.description or "",
        amount_cents=draft.amount_cents or 0,
        method_id=method_id,
        method_type=kind,
        person_id=person_id,
        purchase_date=(draft.purchase_date or dates.today_sp()).isoformat(),
        installments=installments,
        missing=missing,
        sources=sources,
    )
