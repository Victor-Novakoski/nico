"""Configurações da pessoa logada: meio de pagamento principal (decisão 009)."""

from typing import Annotated
from uuid import UUID

import psycopg
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from nico.auth import CurrentUser, current_user
from nico.db import get_conn

router = APIRouter(prefix="/api/me/settings")

Conn = Annotated[psycopg.Connection, Depends(get_conn)]
User = Annotated[CurrentUser, Depends(current_user)]


class SettingsOut(BaseModel):
    default_method_id: UUID | None
    # Somente leitura aqui; ligar e desligar a IA é a issue #35.
    ai_enabled: bool


class SettingsPatch(BaseModel):
    # Obrigatório no corpo: `{}` é 422 e `null` explícito tira o principal.
    default_method_id: UUID | None


def _read(conn: psycopg.Connection, user_id: str) -> SettingsOut:
    row = conn.execute(
        "select default_method_id, ai_enabled from app_user where id = %s", (user_id,)
    ).fetchone()
    return SettingsOut(default_method_id=row[0], ai_enabled=row[1])


@router.get("")
def get_settings(conn: Conn, user: User) -> SettingsOut:
    return _read(conn, user.id)


@router.patch("")
def update_settings(body: SettingsPatch, conn: Conn, user: User) -> SettingsOut:
    if (
        body.default_method_id is not None
        and conn.execute(
            "select 1 from payment_method where id = %s", (body.default_method_id,)
        ).fetchone()
        is None
    ):
        raise HTTPException(status_code=422, detail="Meio de pagamento não encontrado")
    conn.execute(
        "update app_user set default_method_id = %s where id = %s",
        (body.default_method_id, user.id),
    )
    return _read(conn, user.id)
