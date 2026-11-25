"""Rascunhos a partir de uma frase simples, só com regras (decisão 007).

Não grava nada e não chama IA. O que as regras não entendem volta como
`understood: false`, para a tela abrir o formulário ou (depois) a IA.
"""

import re
from typing import Annotated, Literal

import psycopg
from fastapi import APIRouter, Depends
from pydantic import BaseModel, StringConstraints

from nico import dates, rules
from nico.aliases import normalize
from nico.auth import CurrentUser, current_user
from nico.db import get_conn

router = APIRouter(prefix="/api/drafts")

Conn = Annotated[psycopg.Connection, Depends(get_conn)]
User = Annotated[CurrentUser, Depends(current_user)]
Text = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=500)]
Kind = Literal["credito", "debito", "pix", "dinheiro"]
CASH_KINDS = {"debito", "pix", "dinheiro"}

_INSTALLMENT_RE = re.compile(r"\b\d{1,2}\s*x\b", re.IGNORECASE)


class ParseIn(BaseModel):
    text: Text


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


class ParseOut(BaseModel):
    understood: bool
    drafts: list[DraftOut]


def _load_aliases(conn: psycopg.Connection) -> tuple[dict[str, str], dict[str, str]]:
    """({apelido: id do meio}, {id do meio: tipo}).

    Além dos apelidos cadastrados, o próprio nome de cada meio vale como apelido
    (normalizado). Apelido cadastrado vence nome; nome repetido entre meios fica
    com o primeiro (os apelidos são únicos no banco, os nomes não).
    """
    kinds: dict[str, str] = {}
    names: dict[str, str] = {}
    for method_id, name, kind in conn.execute(
        "select id::text, name, kind from payment_method order by name, id"
    ):
        kinds[method_id] = kind
        names.setdefault(normalize(name), method_id)
    aliases: dict[str, str] = {}
    for alias, method_id in conn.execute(
        "select alias, payment_method_id::text from payment_method_alias"
    ):
        aliases[normalize(alias)] = method_id
    for name, method_id in names.items():
        if name:
            aliases.setdefault(name, method_id)
    return aliases, kinds


def _segments(text: str) -> list[str]:
    # Mesma divisão de rules.parse_simple, para casar segmento e rascunho.
    return [s.strip() for s in re.split(r"[\n;]", text) if s.strip()]


def _date_in_text(segment: str, today) -> bool:
    try:
        return dates.parse_date_pt(segment, today) is not None
    except ValueError:
        return False


@router.post("/parse")
def parse_drafts(body: ParseIn, conn: Conn, user: User) -> ParseOut:
    aliases, kinds = _load_aliases(conn)
    row = conn.execute(
        "select default_method_id::text from app_user where id = %s", (user.id,)
    ).fetchone()
    default_method_id = row[0] if row else None
    today = dates.today_sp()
    parsed = rules.parse_simple(body.text, aliases, today)
    if parsed is None:
        return ParseOut(understood=False, drafts=[])
    segments = _segments(body.text)
    drafts = []
    for draft, segment in zip(parsed, segments, strict=True):
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
        drafts.append(
            DraftOut(
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
        )
    return ParseOut(understood=True, drafts=drafts)
