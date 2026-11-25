"""Cascata de provedores de IA (decisão 006). Lógica pura, sem rede.

Passa para o próximo em `ProviderUnavailable`, tempo esgotado ou resposta que não
valida no schema. `ProviderConfigError` levanta na hora. Nunca guarda nem loga o
texto ou o áudio: os motivos são frases curtas fixas.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from typing import Any

from pydantic import ValidationError

from nico.ai.base import AllProvidersFailed, ProviderUnavailable
from nico.ai.schema import Extraction

Provider = tuple[str, Any]
Factory = Callable[[], Any]


class Cascade:
    """Recebe `(nome, provedor)` já na ordem de `AI_PROVIDERS`."""

    def __init__(self, providers: Sequence[Provider]) -> None:
        self.providers = list(providers)

    def extract(self, text: str, context: Any) -> tuple[str, Extraction]:
        """Devolve o nome de quem respondeu e a extração."""
        return self._run("extract", lambda p: p.extract(text, context), _check_extraction)

    def transcribe(self, audio: bytes, mime: str) -> tuple[str, str]:
        """Devolve o nome de quem respondeu e a transcrição."""
        return self._run("transcribe", lambda p: p.transcribe(audio, mime), _check_text)

    def _run(self, method: str, call: Callable[[Any], Any], check: Callable[[Any], Any]):
        reasons: list[tuple[str, str]] = []
        for name, provider in self.providers:
            if not callable(getattr(provider, method, None)):
                continue  # este provedor não faz essa tarefa
            try:
                return name, check(call(provider))
            except ProviderUnavailable:
                reasons.append((name, "indisponível (limite, erro ou tempo esgotado)"))
            except TimeoutError:
                reasons.append((name, "tempo esgotado"))
            except (ValidationError, ValueError):
                reasons.append((name, "resposta inválida"))
        raise AllProvidersFailed(reasons)


def _check_extraction(value: Any) -> Extraction:
    if not isinstance(value, Extraction):
        raise ValueError("resposta fora do schema")
    return value


def _check_text(value: Any) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError("transcrição vazia")
    return value


def build_cascade(names: str | Sequence[str], registry: Mapping[str, Factory]) -> Cascade:
    """Monta a cascata a partir de `AI_PROVIDERS` (ex.: "groq,cloudflare")."""
    if isinstance(names, str):
        names = names.split(",")
    wanted = [n.strip().lower() for n in names if n.strip()]
    unknown = [n for n in wanted if n not in registry]
    if unknown:
        known = ", ".join(sorted(registry)) or "nenhum"
        raise ValueError(
            f"provedor desconhecido em AI_PROVIDERS: {', '.join(unknown)} (conhecidos: {known})"
        )
    return Cascade([(n, registry[n]()) for n in wanted])
