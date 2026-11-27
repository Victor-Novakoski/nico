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

from nico import purchases, scope
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
    group_id: UUID | None = None
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


def _shares_dict(shares: list[ShareIn], me: UUID, members: set[UUID] | None) -> dict[UUID, int]:
    """Divisão no escopo da compra: de grupo (`members`), só membros; pessoal (`None`), só eu."""
    ids = [s.person_id for s in shares]
    if len(set(ids)) != len(ids):
        raise HTTPException(status_code=422, detail="Pessoa repetida na divisão")
    if members is None:
        if any(i != me for i in ids):
            raise HTTPException(
                status_code=422, detail="Compra dividida com outra pessoa precisa de um grupo"
            )
    elif not set(ids) <= members:
        raise HTTPException(status_code=422, detail="Pessoa fora do grupo na divisão")
    return {s.person_id: s.weight for s in shares}


def _not_found() -> HTTPException:
    return HTTPException(status_code=404, detail="Compra não encontrada")


def _method_not_found() -> HTTPException:
    return HTTPException(status_code=422, detail="Meio de pagamento não encontrado")


@router.post("", status_code=201)
def create_purchase(body: PurchaseIn, response: Response, conn: Conn, user: User) -> dict:
    """201 ao criar; reenvio do mesmo `id` devolve a compra existente com 200, sem duplicar."""
    me = UUID(user.person_id)
    exists = conn.execute("select 1 from purchase where id = %s", (body.id,)).fetchone()
    if exists is not None:
        if not scope.can_read_purchase(conn, me, body.id):
            raise _not_found()
        response.status_code = 200
        return _get(conn, body.id)
    members: set[UUID] | None = None
    if body.group_id is not None:
        if not scope.is_member(conn, me, body.group_id):
            raise HTTPException(status_code=404, detail="Grupo não encontrado")
        members = scope.group_members(conn, body.group_id)
    if not scope.owns_method(conn, me, body.payment_method_id):
        raise _method_not_found()
    if body.shares:
        shares = _shares_dict(body.shares, me, members)
    elif members is not None:
        # Compra de grupo sem divisão: partes iguais entre os membros (decisão 013).
        shares = dict.fromkeys(members, 1)
    else:
        shares = None
    try:
        purchases.create_purchase(
            conn,
            id=body.id,
            payment_method_id=body.payment_method_id,
            description=body.description,
            total_cents=body.total_cents,
            purchase_date=body.purchase_date,
            installments=body.installments,
            created_by_person_id=me,
            shares=shares,
            status=body.status,
            ai_provider=body.ai_provider,
            group_id=body.group_id,
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
def list_purchases(conn: Conn, user: User, status: Status | None = None) -> list[dict]:
    rows = conn.execute(
        "select p.id from purchase p where (%(status)s::text is null or p.status = %(status)s)"
        f" and {scope.READABLE_PURCHASE} order by p.purchase_date desc, p.created_at desc, p.id",
        {"status": status, "me": user.person_id},
    ).fetchall()
    return [_get(conn, r[0]) for r in rows]


@router.get("/{purchase_id}")
def get_purchase(purchase_id: UUID, conn: Conn, user: User) -> dict:
    if not scope.can_read_purchase(conn, user.person_id, purchase_id):
        raise _not_found()
    data = _get(conn, purchase_id)
    if data is None:
        raise _not_found()
    return data


@router.patch("/{purchase_id}")
def patch_purchase(purchase_id: UUID, body: PurchasePatch, conn: Conn, user: User) -> dict:
    me = UUID(user.person_id)
    if not scope.can_edit_purchase(conn, me, purchase_id):
        raise _not_found()
    group_id, owner_id = conn.execute(
        "select p.group_id, pm.owner_person_id from purchase p"
        " join payment_method pm on pm.id = p.payment_method_id where p.id = %s",
        (purchase_id,),
    ).fetchone()
    changes: dict[str, Any] = {k: getattr(body, k) for k in body.model_fields_set if k != "shares"}
    if "payment_method_id" in changes:
        # O meio novo tem que ser do dono atual do meio da compra ou de quem edita.
        new_owner = conn.execute(
            "select owner_person_id from payment_method where id = %s",
            (changes["payment_method_id"],),
        ).fetchone()
        if new_owner is None or new_owner[0] not in (owner_id, me):
            raise _method_not_found()
    if "shares" in body.model_fields_set:
        members = None if group_id is None else scope.group_members(conn, group_id)
        changes["shares"] = _shares_dict(body.shares, me, members)
    try:
        found = purchases.update_purchase(conn, purchase_id, **changes)
    except ValueError as error:
        raise HTTPException(status_code=422, detail=_message(error)) from None
    if not found:
        raise _not_found()
    return _get(conn, purchase_id)


@router.delete("/{purchase_id}", status_code=204)
def delete_purchase(purchase_id: UUID, conn: Conn, user: User) -> Response:
    """Apaga a compra (parcelas e divisão vão junto); faturas que ficarem vazias permanecem."""
    if not scope.can_edit_purchase(conn, user.person_id, purchase_id):
        raise _not_found()
    deleted = conn.execute("delete from purchase where id = %s returning id", (purchase_id,))
    if deleted.fetchone() is None:
        raise _not_found()
    return Response(status_code=204)
