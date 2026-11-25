import json
from datetime import date

import httpx
import pytest
from pydantic import ValidationError

from nico.ai import ollama
from nico.ai.base import AllProvidersFailed, ProviderConfigError, ProviderUnavailable
from nico.ai.cascade import Cascade
from nico.ai.ollama import OllamaExtractor
from nico.ai.prompt import ExtractionContext
from nico.ai.registry import provider_registry
from nico.ai.schema import Extraction

CTX = ExtractionContext(today=date(2026, 3, 5))
GOOD_CONTENT = json.dumps({"items": [{"description": "pao", "amount_text": "15"}]})


def make(handler, url="http://ollama.test:11434/"):
    client = httpx.Client(transport=httpx.MockTransport(handler))
    return OllamaExtractor(url, "modelo-teste", client=client)


def ok(request):
    return httpx.Response(200, json={"message": {"role": "assistant", "content": GOOD_CONTENT}})


def test_good_response_and_request_body():
    seen = {}

    def handler(request):
        seen["url"] = str(request.url)
        seen["body"] = json.loads(request.content)
        return ok(request)

    result = make(handler).extract("15 de pao no pix", CTX)
    assert isinstance(result, Extraction)
    assert result.items[0].description == "pao"
    assert seen["url"] == "http://ollama.test:11434/api/chat"
    body = seen["body"]
    assert body["model"] == "modelo-teste"
    assert body["stream"] is False
    assert body["options"] == {"temperature": 0}
    assert "$ref" not in json.dumps(body["format"])
    system, user = body["messages"]
    assert system["role"] == "system" and "05/03/2026" in system["content"]
    assert user == {"role": "user", "content": "15 de pao no pix"}


def test_invalid_json_content():
    def handler(request):
        return httpx.Response(200, json={"message": {"content": "isso nao e json"}})

    with pytest.raises(ValidationError):
        make(handler).extract("x", CTX)


@pytest.mark.parametrize(
    "response",
    [
        httpx.Response(200, json={"outro": 1}),
        httpx.Response(200, json={"message": {}}),
        httpx.Response(200, text="nao e json"),
    ],
)
def test_malformed_body_is_value_error(response):
    with pytest.raises(ValueError, match="fora do formato") as exc:
        make(lambda request: response).extract("frase secreta", CTX)
    assert "frase secreta" not in str(exc.value)


@pytest.mark.parametrize("status", [500, 429])
def test_unavailable_statuses(status):
    with pytest.raises(ProviderUnavailable):
        make(lambda request: httpx.Response(status)).extract("x", CTX)


def test_missing_model_is_config_error():
    with pytest.raises(ProviderConfigError):
        make(lambda request: httpx.Response(404, json={"error": "model not found"})).extract(
            "x", CTX
        )


def test_timeout_is_unavailable():
    def handler(request):
        raise httpx.ReadTimeout("lento", request=request)

    with pytest.raises(ProviderUnavailable):
        make(handler).extract("x", CTX)


def test_cascade_failure_and_success():
    failing = make(lambda request: httpx.Response(500))
    with pytest.raises(AllProvidersFailed) as exc:
        Cascade([("ollama", failing)]).extract("x", CTX)
    assert exc.value.names == ["ollama"]

    name, extraction = Cascade([("ollama", make(ok))]).extract("x", CTX)
    assert name == "ollama"
    assert extraction.items[0].amount_text == "15"


def test_from_env(monkeypatch):
    monkeypatch.delenv("OLLAMA_MODEL", raising=False)
    monkeypatch.delenv("OLLAMA_URL", raising=False)
    with pytest.raises(RuntimeError):
        ollama.from_env()
    monkeypatch.setenv("OLLAMA_MODEL", "modelo-teste")
    extractor = ollama.from_env()
    assert extractor.url == "http://localhost:11434"
    assert extractor.model == "modelo-teste"


def test_registry_builds_ollama(monkeypatch):
    monkeypatch.setenv("OLLAMA_MODEL", "modelo-teste")
    assert isinstance(provider_registry()["ollama"](), OllamaExtractor)
