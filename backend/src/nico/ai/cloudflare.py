"""Provedor Cloudflare Workers AI (decisão 006): extração e transcrição (Whisper).

Usa a REST API `POST /accounts/{id}/ai/run/{model}`. O formato abaixo é uma
suposição a confirmar com a conta real (issue #45):
- extração: resposta `{"success": true, "result": {"response": ...}}`, em que
  `response` é um texto JSON ou um objeto já interpretado;
- transcrição: modelo `@cf/openai/whisper-large-v3-turbo`, que aceita JSON com
  `audio` em base64 e `language`, e devolve `result.text`.

O token, a frase, o áudio e o corpo da resposta nunca entram em mensagem de erro,
log nem `repr`.
"""

from __future__ import annotations

import base64
from typing import Any

import httpx

from nico import config
from nico.ai import http
from nico.ai.audio import check_audio
from nico.ai.base import ProviderConfigError
from nico.ai.prompt import ExtractionContext, extraction_schema, parse_extraction, system_prompt
from nico.ai.schema import Extraction

BASE_URL = "https://api.cloudflare.com/client/v4"


class CloudflareAI:
    def __init__(
        self,
        account_id: str,
        api_token: str,
        model: str,
        whisper_model: str | None = None,
        client: httpx.Client | None = None,
        timeout: float = 30.0,
        base_url: str = BASE_URL,
    ) -> None:
        self.account_id = account_id
        self._api_token = api_token
        self.model = model
        self.whisper_model = whisper_model
        self.timeout = timeout
        self.base_url = base_url.rstrip("/")
        self._client = client or httpx.Client(timeout=timeout)

    def __repr__(self) -> str:
        return f"CloudflareAI(model={self.model!r}, whisper_model={self.whisper_model!r})"

    def _run(self, model: str, payload: dict[str, Any]) -> Any:
        response = http.call(
            lambda: self._client.post(
                f"{self.base_url}/accounts/{self.account_id}/ai/run/{model}",
                headers={"Authorization": f"Bearer {self._api_token}"},
                json=payload,
                timeout=self.timeout,
            )
        )
        try:
            body = response.json()
            success = body["success"]
            result = body["result"]
        except (ValueError, KeyError, TypeError):
            raise ValueError("resposta da Cloudflare fora do formato esperado") from None
        if success is not True:
            raise ValueError("a Cloudflare não concluiu o pedido")
        return result

    def extract(self, text: str, context: ExtractionContext) -> Extraction:
        payload = {
            "messages": [
                {"role": "system", "content": system_prompt(context)},
                {"role": "user", "content": text},
            ],
            "temperature": 0,
            "response_format": {"type": "json_schema", "json_schema": extraction_schema()},
        }
        result = self._run(self.model, payload)
        content = result.get("response") if isinstance(result, dict) else None
        if isinstance(content, str):
            return parse_extraction(content)
        if isinstance(content, dict):
            return Extraction.model_validate(content)
        raise ValueError("resposta da Cloudflare fora do formato esperado")

    def transcribe(self, audio: bytes, mime: str) -> str:
        check_audio(audio, mime)
        if not self.whisper_model:
            raise ProviderConfigError("modelo de transcrição da Cloudflare não configurado")
        payload = {"audio": base64.b64encode(audio).decode(), "language": "pt"}
        result = self._run(self.whisper_model, payload)
        text = result.get("text") if isinstance(result, dict) else None
        if not isinstance(text, str):
            raise ValueError("resposta da Cloudflare fora do formato esperado")
        return text


def from_env() -> CloudflareAI:
    return CloudflareAI(
        config.require("CLOUDFLARE_ACCOUNT_ID"),
        config.require("CLOUDFLARE_API_TOKEN"),
        config.require("CLOUDFLARE_MODEL"),
        whisper_model=config.optional("CLOUDFLARE_WHISPER_MODEL", "") or None,
    )
