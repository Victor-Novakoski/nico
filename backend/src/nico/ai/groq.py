"""Provedor de extração Groq (decisão 006), API compatível com a da OpenAI.

A chave, a frase, o prompt e o corpo da resposta nunca entram em mensagem de erro,
log nem `repr`. O mesmo objeto extrai e transcreve (a cascata guarda um por nome).
"""

from __future__ import annotations

import httpx

from nico import config
from nico.ai import http
from nico.ai.audio import EXTENSIONS, check_audio
from nico.ai.base import ProviderConfigError
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
        whisper_model: str | None = None,
    ) -> None:
        self._api_key = api_key
        self.model = model
        self.whisper_model = whisper_model
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

    def transcribe(self, audio: bytes, mime: str) -> str:
        kind = check_audio(audio, mime)
        if self.whisper_model is None:
            raise ProviderConfigError("GROQ_WHISPER_MODEL não definido")
        model = self.whisper_model
        response = http.call(
            lambda: self._client.post(
                f"{self.base_url}/audio/transcriptions",
                headers={"Authorization": f"Bearer {self._api_key}"},
                data={
                    "model": model,
                    "language": "pt",
                    "response_format": "json",
                    "temperature": "0",
                },
                files={"file": (f"audio.{EXTENSIONS[kind]}", audio, kind)},
                timeout=self.timeout,
            )
        )
        try:
            text = response.json()["text"]
        except (ValueError, KeyError, TypeError):
            raise ValueError("resposta do Groq fora do formato esperado") from None
        if not isinstance(text, str):
            raise ValueError("resposta do Groq fora do formato esperado")
        return text


Groq = GroqExtractor


def from_env() -> GroqExtractor:
    return GroqExtractor(
        config.require("GROQ_API_KEY"),
        config.require("GROQ_MODEL"),
        whisper_model=config.optional("GROQ_WHISPER_MODEL", "") or None,
    )
