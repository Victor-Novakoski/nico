"""Hash e verificação de senha com scrypt (stdlib).

Formato: `scrypt$n$r$p$sal_hex$hash_hex`. Os parâmetros ficam no próprio hash,
então dá para mudá-los depois sem invalidar senhas já gravadas.
"""

import hashlib
import hmac
import secrets

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
