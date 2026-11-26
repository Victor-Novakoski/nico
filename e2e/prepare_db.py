"""Prepara o banco do E2E: zera o schema, aplica as migrações e cria o usuário de teste.

Variáveis: DATABASE_URL (banco SÓ de teste, será apagado), E2E_USERNAME, E2E_PASSWORD.
A senha vem do ambiente; nunca é escrita no repositório.
"""

import os
import sys
from urllib.parse import urlparse

import psycopg

from nico.create_user import create_user
from nico.migrate import migrate


def main() -> int:
    url = os.environ.get("DATABASE_URL")
    password = os.environ.get("E2E_PASSWORD")
    if not url or not password:
        print("Defina DATABASE_URL e E2E_PASSWORD.", file=sys.stderr)
        return 1
    # Trava: este script apaga o banco; só aceita Postgres local (CI e docker compose).
    if urlparse(url).hostname not in {"localhost", "127.0.0.1", "::1"}:
        print("Recusado: o E2E só zera banco local.", file=sys.stderr)
        return 1
    with psycopg.connect(url, autocommit=True) as conn:
        conn.execute("drop schema public cascade")
        conn.execute("create schema public")
    migrate(url)
    create_user(url, os.environ.get("E2E_USERNAME", "e2e"), "Pessoa de Teste", password)
    print("Banco do E2E pronto.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
