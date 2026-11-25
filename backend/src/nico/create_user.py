"""Cria um usuário pelo terminal: `python -m nico.create_user <username> <nome da pessoa>`.

Lê DATABASE_URL. Se a pessoa não existir, cria. A senha é pedida com getpass
(nunca por argumento) e não é impressa.
"""

import getpass
import sys

import psycopg

from nico import config
from nico.auth import hash_password

MIN_PASSWORD = 8


def create_user(database_url: str, username: str, person_name: str, password: str) -> None:
    with psycopg.connect(database_url) as conn:
        row = conn.execute(
            "select id from person where name = %s order by id limit 1", (person_name,)
        ).fetchone()
        if row:
            person_id = row[0]
        else:
            person_id = conn.execute(
                "insert into person (name) values (%s) returning id", (person_name,)
            ).fetchone()[0]
        conn.execute(
            "insert into app_user (person_id, username, password_hash) values (%s, %s, %s)",
            (person_id, username, hash_password(password)),
        )


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    if len(args) < 2:
        print("Uso: python -m nico.create_user <username> <nome da pessoa>", file=sys.stderr)
        return 1
    username = args[0].strip()
    person_name = " ".join(args[1:]).strip()
    if not username or not person_name:
        print("Usuário e nome da pessoa não podem ser vazios.", file=sys.stderr)
        return 1
    try:
        url = config.require("DATABASE_URL")
    except RuntimeError as exc:
        print(exc, file=sys.stderr)
        return 1
    password = getpass.getpass("Senha: ")
    if getpass.getpass("Repita a senha: ") != password:
        print("As senhas não são iguais.", file=sys.stderr)
        return 1
    if len(password) < MIN_PASSWORD:
        print(f"A senha precisa ter pelo menos {MIN_PASSWORD} caracteres.", file=sys.stderr)
        return 1
    try:
        create_user(url, username, person_name, password)
    except psycopg.errors.UniqueViolation:
        print(f"O usuário '{username}' já existe.", file=sys.stderr)
        return 1
    except psycopg.Error:
        print("Não foi possível gravar no banco.", file=sys.stderr)
        return 1
    print(f"Usuário '{username}' criado para {person_name}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
