"""Aplica as migrações SQL de `backend/migrations/` em ordem.

Uso: `python -m nico.migrate` (lê DATABASE_URL). Cada arquivo roda numa transação
e fica registrado em `schema_migrations`; rodar de novo não faz nada.
"""

import os
import sys
from pathlib import Path

import psycopg

MIGRATIONS_DIR = Path(__file__).resolve().parents[2] / "migrations"
LOCK_KEY = 8_426_001  # advisory lock: duas execuções ao mesmo tempo não se atropelam


def migrate(database_url: str, directory: Path = MIGRATIONS_DIR) -> list[str]:
    """Aplica as migrações pendentes e devolve os nomes aplicados agora."""
    applied: list[str] = []
    with psycopg.connect(database_url, autocommit=True) as conn:
        conn.execute("select pg_advisory_lock(%s)", (LOCK_KEY,))
        try:
            conn.execute(
                "create table if not exists schema_migrations ("
                "name text primary key, applied_at timestamptz not null default now())"
            )
            done = {row[0] for row in conn.execute("select name from schema_migrations")}
            for path in sorted(directory.glob("*.sql")):
                if path.name in done:
                    continue
                with conn.transaction():
                    conn.execute(path.read_text(encoding="utf-8"))
                    conn.execute("insert into schema_migrations (name) values (%s)", (path.name,))
                applied.append(path.name)
        finally:
            conn.execute("select pg_advisory_unlock(%s)", (LOCK_KEY,))
    return applied


def main() -> int:
    url = os.environ.get("DATABASE_URL")
    if not url:
        print("Defina DATABASE_URL.", file=sys.stderr)
        return 1
    applied = migrate(url)
    print(f"Aplicadas: {', '.join(applied)}" if applied else "Nada a aplicar.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
