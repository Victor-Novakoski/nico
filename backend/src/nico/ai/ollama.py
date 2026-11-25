"""Provedor de extração Ollama (decisão 006): local, para desenvolver e para os evals.

Não transcreve áudio. Mensagens de erro são fixas: nunca levam a frase, o prompt
nem o corpo da resposta.
"""

from __future__ import annotations

import httpx

from nico import config
from nico.ai.http import call
from nico.ai.prompt import ExtractionContext, extraction_schema, parse_extraction, system_prompt
from nico.ai.schema import Extraction


class OllamaExtractor:
    def __init__(
        self,
        url: str,
        model: str,
        client: httpx.Client | None = None,
        timeout: float = 60.0,
    ) -> None:
        self.url = url.rstrip("/")
        self.model = model
        self.client = client or httpx.Client(timeout=timeout)
        self.timeout = timeout

    def extract(self, text: str, context: ExtractionContext) -> Extraction:
        body = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt(context)},
                {"role": "user", "content": text},
            ],
            "format": extraction_schema(),
            "stream": False,
            "options": {"temperature": 0},
        }
        response = call(
            lambda: self.client.post(f"{self.url}/api/chat", json=body, timeout=self.timeout)
        )
        try:
            content = response.json()["message"]["content"]
        except (ValueError, KeyError, TypeError) as e:
            raise ValueError("resposta do Ollama fora do formato esperado") from e
        if not isinstance(content, str):
            raise ValueError("resposta do Ollama fora do formato esperado")
        return parse_extraction(content)


def from_env() -> OllamaExtractor:
    return OllamaExtractor(
        config.optional("OLLAMA_URL", "http://localhost:11434"),
        config.require("OLLAMA_MODEL"),
    )
