"""Conexão com o Postgres: pool criado no `lifespan` e dependência `get_conn`."""

from collections.abc import AsyncIterator, Iterator
from contextlib import asynccontextmanager

import psycopg
from fastapi import FastAPI, HTTPException, Request
from psycopg_pool import ConnectionPool

from nico import config


def create_pool() -> ConnectionPool:
    """Abre o pool a partir de DATABASE_URL (obrigatória só aqui).

    Pool pequeno de propósito: na hospedagem serverless cada instância abre o seu, e o
    plano grátis do Neon limita conexões (o padrão do psycopg_pool abriria 4 de cara).
    """
    return ConnectionPool(config.require("DATABASE_URL"), min_size=1, max_size=4, open=True)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Cria o pool se DATABASE_URL existir; sem ela o app sobe só sem banco."""
    app.state.pool = create_pool() if config.optional("DATABASE_URL", "") else None
    try:
        yield
    finally:
        if app.state.pool is not None:
            app.state.pool.close()


def get_conn(request: Request) -> Iterator[psycopg.Connection]:
    """Uma conexão por requisição, numa transação: commit no fim, rollback se der erro."""
    pool: ConnectionPool | None = getattr(request.app.state, "pool", None)
    if pool is None:
        raise HTTPException(status_code=503, detail="Banco de dados indisponível")
    with pool.connection() as conn:
        yield conn
