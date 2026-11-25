"""Configurações da pessoa logada: meio de pagamento principal (decisão 009)."""

from typing import Annotated
from uuid import UUID

import psycopg
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, StrictBool, model_validator

from nico.auth import CurrentUser, current_user
from nico.db import get_conn

router = APIRouter(prefix="/api/me/settings")

Conn = Annotated[psycopg.Connection, Depends(get_conn)]
User = Annotated[CurrentUser, Depends(current_user)]


class SettingsOut(BaseModel):
    default_method_id: UUID | None
    ai_enabled: bool


class SettingsPatch(BaseModel):
    """Atualização parcial: só muda o que veio no corpo; `null` em `default_method_id` limpa."""

    model_config = ConfigDict(extra="forbid")

    default_method_id: UUID | None = None
    ai_enabled: StrictBool | None = None

    @model_validator(mode="after")
    def _check_fields(self) -> "SettingsPatch":
        if not self.model_fields_set:
            raise ValueError("Informe ao menos um campo")
        if "ai_enabled" in self.model_fields_set and self.ai_enabled is None:
            raise ValueError("ai_enabled não aceita null")
        return self


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
    sent = body.model_fields_set
    if (
        "default_method_id" in sent
        and body.default_method_id is not None
        and conn.execute(
            "select 1 from payment_method where id = %s", (body.default_method_id,)
        ).fetchone()
        is None
    ):
        raise HTTPException(status_code=422, detail="Meio de pagamento não encontrado")
    sets: list[str] = []
    params: list[object] = []
    if "default_method_id" in sent:
        sets.append("default_method_id = %s")
        params.append(body.default_method_id)
    if "ai_enabled" in sent:
        sets.append("ai_enabled = %s")
        params.append(body.ai_enabled)
    conn.execute(f"update app_user set {', '.join(sets)} where id = %s", (*params, user.id))
    return _read(conn, user.id)
