"""Login, logout e usuário atual (cookie de sessão HttpOnly)."""

import time

import psycopg
from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel

from nico.auth import (
    SESSION_COOKIE,
    SESSION_SECONDS,
    CurrentUser,
    current_user,
    sign_session,
    verify_password,
)
from nico.db import get_conn

router = APIRouter(prefix="/api")

MAX_FAILURES = 5
WINDOW_SECONDS = 15 * 60

# Limite em memória: vale por instância (na hospedagem serverless cada uma tem o seu).
_failures: dict[str, list[float]] = {}


def _now() -> float:
    return time.monotonic()


def reset_limiter() -> None:
    _failures.clear()


def _recent_failures(username: str) -> list[float]:
    limit = _now() - WINDOW_SECONDS
    recent = [t for t in _failures.get(username, []) if t > limit]
    if recent:
        _failures[username] = recent
    else:
        _failures.pop(username, None)
    return recent


class LoginBody(BaseModel):
    username: str
    password: str


def _cookie_args() -> dict:
    return {"httponly": True, "secure": True, "samesite": "lax", "path": "/"}


@router.post("/login")
def login(
    body: LoginBody, response: Response, conn: psycopg.Connection = Depends(get_conn)
) -> dict[str, str]:
    if len(_recent_failures(body.username)) >= MAX_FAILURES:
        raise HTTPException(
            status_code=429, detail="Muitas tentativas. Tente de novo em alguns minutos."
        )
    row = conn.execute(
        "select id::text, password_hash from app_user where username = %s", (body.username,)
    ).fetchone()
    # Verifica mesmo sem usuário (hash de fachada) para não revelar quem existe pelo tempo.
    stored = row[1] if row else _DUMMY_HASH
    if not verify_password(body.password, stored) or row is None:
        _failures.setdefault(body.username, []).append(_now())
        raise HTTPException(status_code=401, detail="Usuário ou senha incorretos")
    _failures.pop(body.username, None)
    response.set_cookie(
        SESSION_COOKIE, sign_session(row[0]), max_age=SESSION_SECONDS, **_cookie_args()
    )
    return {"username": body.username}


_DUMMY_HASH = "scrypt$16384$8$1$" + "00" * 16 + "$" + "00" * 32


@router.post("/logout", status_code=204)
def logout(response: Response, user: CurrentUser = Depends(current_user)) -> None:
    response.delete_cookie(SESSION_COOKIE, **_cookie_args())


@router.get("/me")
def me(user: CurrentUser = Depends(current_user)) -> dict[str, str]:
    return {"username": user.username, "person_id": user.person_id}
