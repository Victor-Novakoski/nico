"""Lançar, listar, editar, conferir e apagar compras (decisões 002, 009 e 010).

Valor, parcelas e faturas são calculados por `nico.purchases`; aqui só se valida a entrada.
Quem lançou (`created_by_person_id`) vem sempre do usuário logado, nunca do corpo.
"""

from datetime import date
from typing import Annotated, Any, Literal
from uuid import UUID

import psycopg
from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel, ConfigDict, Field, StrictInt, StringConstraints, model_validator

from nico import purchases
from nico.auth import CurrentUser, current_user
from nico.db import get_conn

router = APIRouter(prefix="/api/purchases")

Conn = Annotated[psycopg.Connection, Depends(get_conn)]
User = Annotated[CurrentUser, Depends(current_user)]
Description = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]
Cents = Annotated[StrictInt, Field(ge=0)]
Installments = Annotated[StrictInt, Field(ge=1)]
Status = Literal["pendente", "conferido"]


class ShareIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    person_id: UUID
    weight: Annotated[StrictInt, Field(gt=0)]


class PurchaseIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: UUID
    payment_method_id: UUID
    description: Description
    total_cents: Cents
    purchase_date: date
    installments: Installments = 1
    status: Status = "pendente"
    shares: list[ShareIn] | None = None
    ai_provider: Annotated[str, StringConstraints(max_length=80)] | None = None


class PurchasePatch(BaseModel):
    """Campos ausentes ficam como estão; `null` explícito é recusado (nenhum campo é anulável)."""

    model_config = ConfigDict(extra="forbid")

    description: Description = None  # type: ignore[assignment]
    total_cents: Cents = None  # type: ignore[assignment]
    payment_method_id: UUID = None  # type: ignore[assignment]
    purchase_date: date = None  # type: ignore[assignment]
    installments: Installments = None  # type: ignore[assignment]
    status: Status = None  # type: ignore[assignment]
    shares: list[ShareIn] = None  # type: ignore[assignment]

    @model_validator(mode="after")
    def _not_empty(self) -> "PurchasePatch":
        if not self.model_fields_set:
            raise ValueError("Informe ao menos um campo para alterar")
        return self


def _get(conn: psycopg.Connection, purchase_id: UUID) -> dict[str, Any] | None:
    data = purchases.get_purchase(conn, purchase_id)
    if data is None:
        return None
    return {
        **{k: v for k, v in data.items() if k not in ("shares", "installments_list")},
        "shares": [
            {"person_id": person_id, "weight": weight}
            for person_id, weight in sorted(data["shares"].items(), key=lambda kv: str(kv[0]))
        ],
        "installments_list": [
            {
                "number": i["number"],
                "amount_cents": i["amount_cents"],
                "invoice": {
                    "year": i["year"],
                    "month": i["month"],
                    "closing_date": i["closing_date"],
                    "due_date": i["due_date"],
                },
            }
            for i in data["installments_list"]
        ],
    }


def _shares_dict(conn: psycopg.Connection, shares: list[ShareIn]) -> dict[UUID, int]:
    ids = [s.person_id for s in shares]
    if len(set(ids)) != len(ids):
        raise HTTPException(status_code=422, detail="Pessoa repetida na divisão")
    known = {r[0] for r in conn.execute("select id from person where id = any(%s)", (ids,))}
    if missing := set(ids) - known:
        raise HTTPException(
            status_code=422, detail=f"Pessoa não encontrada: {min(missing, key=str)}"
        )
    return {s.person_id: s.weight for s in shares}


def _not_found() -> HTTPException:
    return HTTPException(status_code=404, detail="Compra não encontrada")


@router.post("", status_code=201)
def create_purchase(body: PurchaseIn, response: Response, conn: Conn, user: User) -> dict:
    """201 ao criar; reenvio do mesmo `id` devolve a compra existente com 200, sem duplicar."""
    if (existing := _get(conn, body.id)) is not None:
        response.status_code = 200
        return existing
    shares = _shares_dict(conn, body.shares) if body.shares else None
    try:
        purchases.create_purchase(
            conn,
            id=body.id,
            payment_method_id=body.payment_method_id,
            description=body.description,
            total_cents=body.total_cents,
            purchase_date=body.purchase_date,
            installments=body.installments,
            created_by_person_id=UUID(user.person_id),
            shares=shares,
            status=body.status,
            ai_provider=body.ai_provider,
        )
    except ValueError as error:
        raise HTTPException(status_code=422, detail=_message(error)) from None
    return _get(conn, body.id)


def _message(error: ValueError) -> str:
    text = str(error)
    if text.startswith("meio de pagamento desconhecido"):
        return "Meio de pagamento não encontrado"
    if text.startswith("compra à vista"):
        return "Compra à vista (débito, Pix ou dinheiro) não pode ser parcelada"
    return text


@router.get("")
def list_purchases(conn: Conn, status: Status | None = None) -> list[dict]:
    rows = conn.execute(
        "select id from purchase where (%s::text is null or status = %s)"
        " order by purchase_date desc, created_at desc, id",
        (status, status),
    ).fetchall()
    return [_get(conn, r[0]) for r in rows]


@router.get("/{purchase_id}")
def get_purchase(purchase_id: UUID, conn: Conn) -> dict:
    data = _get(conn, purchase_id)
    if data is None:
        raise _not_found()
    return data


@router.patch("/{purchase_id}")
def patch_purchase(purchase_id: UUID, body: PurchasePatch, conn: Conn) -> dict:
    changes: dict[str, Any] = {k: getattr(body, k) for k in body.model_fields_set if k != "shares"}
    if "shares" in body.model_fields_set:
        changes["shares"] = _shares_dict(conn, body.shares)
    try:
        found = purchases.update_purchase(conn, purchase_id, **changes)
    except ValueError as error:
        raise HTTPException(status_code=422, detail=_message(error)) from None
    if not found:
        raise _not_found()
    return _get(conn, purchase_id)


@router.delete("/{purchase_id}", status_code=204)
def delete_purchase(purchase_id: UUID, conn: Conn) -> Response:
    """Apaga a compra (parcelas e divisão vão junto); faturas que ficarem vazias permanecem."""
    deleted = conn.execute("delete from purchase where id = %s returning id", (purchase_id,))
    if deleted.fetchone() is None:
        raise _not_found()
    return Response(status_code=204)
