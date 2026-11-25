"""Configuração lida de variáveis de ambiente.

Segredos nunca têm valor padrão: se faltar, falha na hora de usar (`require`).
Não há variáveis hoje; quando uma entrar, declare aqui e em `.env.example`.
"""

import os


def require(name: str) -> str:
    """Lê um segredo obrigatório; erro claro se a variável não existir."""
    value = os.environ.get(name)
    if not value:
        raise RuntimeError(f"Variável de ambiente {name} não definida")
    return value


def optional(name: str, default: str) -> str:
    """Lê uma opção não secreta, com valor padrão."""
    return os.environ.get(name, default)
