"""Interfaces dos provedores de IA e os erros que eles levantam (decisão 006).

Sem rede: os provedores reais (outra issue) traduzem os erros do HTTP para estas
exceções. As mensagens nunca levam o texto da pessoa nem o áudio.
"""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

from nico.ai.schema import Extraction


class ProviderUnavailable(Exception):
    """Limite (429), erro do servidor (5xx) ou tempo esgotado: passa para o próximo."""


class ProviderConfigError(Exception):
    """Chave inválida (401) ou configuração errada: não passa adiante, levanta."""


class AllProvidersFailed(Exception):
    """Nenhum provedor respondeu. `reasons` é uma lista de (nome, motivo curto)."""

    def __init__(self, reasons: list[tuple[str, str]]) -> None:
        self.reasons = reasons
        detail = ", ".join(f"{name}: {why}" for name, why in reasons) or "nenhum provedor"
        super().__init__(f"todos os provedores falharam ({detail})")

    @property
    def names(self) -> list[str]:
        return [name for name, _ in self.reasons]


@runtime_checkable
class Extractor(Protocol):
    def extract(self, text: str, context: Any) -> Extraction: ...


@runtime_checkable
class Transcriber(Protocol):
    def transcribe(self, audio: bytes, mime: str) -> str: ...
