"""Provedor de extração OpenRouter (decisão 006), API compatível com a da OpenAI.

Toda requisição leva `provider.data_collection = "deny"`: o corpo é montado numa função
só (`_build_payload`), então nenhum caminho envia sem a restrição. A chave, a frase, o
prompt e o corpo da resposta nunca entram em mensagem de erro, log nem `repr`.
Transcrição não é feita aqui.
"""

from __future__ import annotations

from typing import Any

import httpx

from nico import config
from nico.ai import http
from nico.ai.base import ProviderConfigError, ProviderUnavailable
from nico.ai.prompt import ExtractionContext, extraction_schema, parse_extraction, system_prompt
from nico.ai.schema import Extraction

BASE_URL = "https://openrouter.ai/api/v1"
DATA_COLLECTION = "deny"


def _build_payload(model: str, text: str, context: ExtractionContext) -> dict[str, Any]:
    """Único lugar que monta o corpo; sempre proíbe a coleta de dados."""
    return {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt(context)},
            {"role": "user", "content": text},
        ],
        "temperature": 0,
        "response_format": {
            "type": "json_schema",
            "json_schema": {"name": "extraction", "schema": extraction_schema()},
        },
        "provider": {"data_collection": DATA_COLLECTION, "require_parameters": True},
    }


def _check_error_body(data: Any) -> None:
    """O OpenRouter pode devolver HTTP 200 com um objeto `error` no corpo."""
    if not isinstance(data, dict) or "error" not in data:
        return
    error = data["error"]
    code = error.get("code") if isinstance(error, dict) else None
    if isinstance(code, int) and not isinstance(code, bool):
        if code == 429 or code >= 500:
            raise ProviderUnavailable(f"erro do provedor ({code})")
        if code in (401, 403):
            raise ProviderConfigError(f"chave recusada pelo provedor ({code})")
    raise ValueError("resposta do OpenRouter com erro")


class OpenRouterExtractor:
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
        return f"OpenRouterExtractor(model={self.model!r})"

    def extract(self, text: str, context: ExtractionContext) -> Extraction:
        payload = _build_payload(self.model, text, context)
        response = http.call(
            lambda: self._client.post(
                f"{self.base_url}/chat/completions",
                headers={"Authorization": f"Bearer {self._api_key}"},
                json=payload,
                timeout=self.timeout,
            )
        )
        try:
            data = response.json()
        except ValueError:
            raise ValueError("resposta do OpenRouter fora do formato esperado") from None
        _check_error_body(data)
        try:
            content = data["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError):
            raise ValueError("resposta do OpenRouter fora do formato esperado") from None
        if not isinstance(content, str):
            raise ValueError("resposta do OpenRouter fora do formato esperado")
        return parse_extraction(content)


def from_env() -> OpenRouterExtractor:
    return OpenRouterExtractor(
        config.require("OPENROUTER_API_KEY"), config.require("OPENROUTER_MODEL")
    )
