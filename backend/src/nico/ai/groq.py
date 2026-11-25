"""Provedor de extração Groq (decisão 006), API compatível com a da OpenAI.

A chave, a frase, o prompt e o corpo da resposta nunca entram em mensagem de erro,
log nem `repr`. Transcrição é outra issue.
"""

from __future__ import annotations

import httpx

from nico import config
from nico.ai import http
from nico.ai.prompt import ExtractionContext, extraction_schema, parse_extraction, system_prompt
from nico.ai.schema import Extraction

BASE_URL = "https://api.groq.com/openai/v1"


class GroqExtractor:
    def __init__(
        self,
        api_key: str,
        model: str,
        client: httpx.Client | None = None,
        timeout: float = 30.0,
        base_url: str = BASE_URL,
    ) -> None:
        self._api_key = api_key
        self.model = model
        self.timeout = timeout
        self.base_url = base_url.rstrip("/")
        self._client = client or httpx.Client(timeout=timeout)

    def __repr__(self) -> str:
        return f"GroqExtractor(model={self.model!r})"

    def extract(self, text: str, context: ExtractionContext) -> Extraction:
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt(context)},
                {"role": "user", "content": text},
            ],
            "temperature": 0,
            "response_format": {
                "type": "json_schema",
                "json_schema": {"name": "extraction", "schema": extraction_schema()},
            },
        }
        response = http.call(
            lambda: self._client.post(
                f"{self.base_url}/chat/completions",
                headers={"Authorization": f"Bearer {self._api_key}"},
                json=payload,
                timeout=self.timeout,
            )
        )
        try:
            content = response.json()["choices"][0]["message"]["content"]
        except (ValueError, KeyError, IndexError, TypeError):
            raise ValueError("resposta do Groq fora do formato esperado") from None
        if not isinstance(content, str):
            raise ValueError("resposta do Groq fora do formato esperado")
        return parse_extraction(content)


def from_env() -> GroqExtractor:
    return GroqExtractor(config.require("GROQ_API_KEY"), config.require("GROQ_MODEL"))
