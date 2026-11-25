"""Hash e verificação de senha com scrypt (stdlib) e token de sessão assinado.

Formato: `scrypt$n$r$p$sal_hex$hash_hex`. Os parâmetros ficam no próprio hash,
então dá para mudá-los depois sem invalidar senhas já gravadas.
"""

import base64
import hashlib
import hmac
import secrets
import time
import uuid
from dataclasses import dataclass

import psycopg
from fastapi import Depends, HTTPException, Request

from nico import config
from nico.db import get_conn

SESSION_COOKIE = "nico_session"
SESSION_SECONDS = 30 * 24 * 60 * 60

N = 2**14
R = 8
P = 1
SALT_BYTES = 16
KEY_BYTES = 32
MAX_MEM = 64 * 1024 * 1024


def _derive(password: str, salt: bytes, n: int, r: int, p: int, length: int) -> bytes:
    return hashlib.scrypt(
        password.encode("utf-8"), salt=salt, n=n, r=r, p=p, dklen=length, maxmem=MAX_MEM
    )


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(SALT_BYTES)
    key = _derive(password, salt, N, R, P, KEY_BYTES)
    return f"scrypt${N}${R}${P}${salt.hex()}${key.hex()}"


def verify_password(password: str, stored: str) -> bool:
    """Falso para senha errada ou hash malformado; nunca levanta nem expõe a senha."""
    try:
        scheme, n, r, p, salt_hex, key_hex = stored.split("$")
        if scheme != "scrypt":
            return False
        expected = bytes.fromhex(key_hex)
        key = _derive(password, bytes.fromhex(salt_hex), int(n), int(r), int(p), len(expected))
    except (ValueError, MemoryError):
        return False
    return hmac.compare_digest(key, expected)


def _sign(payload: bytes) -> str:
    key = config.require("NICO_SECRET_KEY").encode("utf-8")
    return hmac.new(key, payload, hashlib.sha256).hexdigest()


def sign_session(user_id: str, now: float | None = None) -> str:
    """Token `base64url(id.expiração).assinatura` (HMAC-SHA256 com NICO_SECRET_KEY)."""
    expires = int((time.time() if now is None else now) + SESSION_SECONDS)
    payload = f"{user_id}.{expires}".encode()
    return f"{base64.urlsafe_b64encode(payload).decode()}.{_sign(payload)}"


def verify_session(token: str, now: float | None = None) -> str | None:
    """Id do usuário se o token é válido e não expirou; senão None. Nunca levanta."""
    try:
        encoded, signature = token.split(".")
        payload = base64.urlsafe_b64decode(encoded.encode())
        if not hmac.compare_digest(_sign(payload), signature):
            return None
        user_id, expires = payload.decode().rsplit(".", 1)
        if (time.time() if now is None else now) >= int(expires):
            return None
    except (ValueError, TypeError):  # UnicodeError é ValueError; TypeError: não ASCII
        return None
    return user_id


@dataclass(frozen=True)
class CurrentUser:
    id: str
    person_id: str
    username: str


def _unauthorized() -> HTTPException:
    return HTTPException(status_code=401, detail="Faça login para continuar")


def session_user_id(request: Request) -> str:
    """Id do usuário no cookie de sessão; 401 sem cookie ou com cookie inválido.

    Não toca no banco: sem cookie a resposta é 401 mesmo com o banco fora do ar.
    """
    token = request.cookies.get(SESSION_COOKIE)
    user_id = verify_session(token) if token else None
    if user_id is None:
        raise _unauthorized()
    return user_id


def current_user(
    user_id: str = Depends(session_user_id), conn: psycopg.Connection = Depends(get_conn)
) -> CurrentUser:
    """Usuário logado, conferido no banco (401 se não existe mais).

    Rotas que gravam compras usam `person_id` daqui como `created_by_person_id`,
    nunca um valor vindo do corpo da requisição.
    """
    try:
        uid = uuid.UUID(user_id)
    except ValueError:
        raise _unauthorized() from None
    row = conn.execute(
        "select id::text, person_id::text, username from app_user where id = %s", (uid,)
    ).fetchone()
    if row is None:
        raise _unauthorized()
    return CurrentUser(id=row[0], person_id=row[1], username=row[2])
