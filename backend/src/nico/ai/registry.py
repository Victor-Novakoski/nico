"""Nome em `AI_PROVIDERS` → fábrica do provedor, para `build_cascade` (decisão 006).

Cada módulo de provedor expõe `from_env()`, que lê a própria configuração. O import é
tardio: só o provedor pedido em `AI_PROVIDERS` é carregado, e falta de variável só
aparece para ele. Provedor novo = módulo novo com `from_env()` e uma linha aqui.
"""

from __future__ import annotations

import importlib
from collections.abc import Callable
from typing import Any

MODULES = {
    "groq": "nico.ai.groq",
    "cloudflare": "nico.ai.cloudflare",
    "openrouter": "nico.ai.openrouter",
    "ollama": "nico.ai.ollama",
}


def _factory(module: str) -> Callable[[], Any]:
    def build() -> Any:
        return importlib.import_module(module).from_env()

    return build


def provider_registry() -> dict[str, Callable[[], Any]]:
    return {name: _factory(module) for name, module in MODULES.items()}
