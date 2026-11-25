import base64
import json
from datetime import date

import httpx
import pytest
from pydantic import ValidationError

from nico.ai import registry
from nico.ai.audio import AudioRejected
from nico.ai.base import ProviderConfigError, ProviderUnavailable
from nico.ai.cascade import Cascade
from nico.ai.cloudflare import BASE_URL, CloudflareAI, from_env
from nico.ai.prompt import ExtractionContext
from nico.ai.schema import ExtractedItem, Extraction, Method, Person

ACCOUNT = "acct-test"
TOKEN = "test-token-abc123"
MODEL = "@cf/modelo/teste"
WHISPER = "@cf/openai/whisper-large-v3-turbo"
TEXT = "42 de pizza no cartão roxo"
CTX = ExtractionContext(
    today=date(2026, 3, 10),
    methods=[Method("m1", ["roxo"], "credito")],
    people=[Person("p1", ["Ana"])],
)
GOOD = {"items": [{"description": "pizza", "amount_text": "42", "method": "roxo"}]}
AUDIO = b"\x1aE\xdf\xa3fake-audio"


def envelope(result, success: bool = True) -> dict:
    return {"success": success, "errors": [], "messages": [], "result": result}


def make(handler, whisper_model: str | None = WHISPER, **kw) -> CloudflareAI:
    client = httpx.Client(transport=httpx.MockTransport(handler))
    return CloudflareAI(ACCOUNT, TOKEN, MODEL, whisper_model=whisper_model, client=client, **kw)


def ok(_request: httpx.Request) -> httpx.Response:
    return httpx.Response(200, json=envelope({"response": json.dumps(GOOD)}))


class FakeOk:
    def extract(self, text, context):
        return Extraction(items=[ExtractedItem(description="outro")])


def test_extract_string_response_builds_request():
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        seen["auth"] = request.headers["authorization"]
        seen["body"] = json.loads(request.content)
        return ok(request)

    result = make(handler).extract(TEXT, CTX)
    assert result.items[0].description == "pizza"
    assert seen["url"] == f"{BASE_URL}/accounts/{ACCOUNT}/ai/run/{MODEL}"
    assert seen["auth"] == f"Bearer {TOKEN}"
    body = seen["body"]
    assert body["temperature"] == 0
    rf = body["response_format"]
    assert rf["type"] == "json_schema"
    assert "$ref" not in json.dumps(rf["json_schema"])
    assert [m["role"] for m in body["messages"]] == ["system", "user"]
    assert body["messages"][1]["content"] == TEXT
    assert "roxo" in body["messages"][0]["content"]


def test_extract_dict_response():
    g = make(lambda r: httpx.Response(200, json=envelope({"response": GOOD})))
    assert g.extract(TEXT, CTX).items[0].description == "pizza"


def test_success_false_is_value_error():
    g = make(lambda r: httpx.Response(200, json=envelope(None, success=False)))
    with pytest.raises(ValueError, match="não concluiu"):
        g.extract(TEXT, CTX)


def test_invalid_json_string_is_validation_error():
    g = make(lambda r: httpx.Response(200, json=envelope({"response": "isso não é json"})))
    with pytest.raises(ValidationError):
        g.extract(TEXT, CTX)


@pytest.mark.parametrize(
    "response",
    [
        httpx.Response(200, json={"id": "x"}),
        httpx.Response(200, json=envelope({"response": 42})),
        httpx.Response(200, json=envelope({})),
        httpx.Response(200, json=envelope("texto")),
        httpx.Response(200, text="<html>não é json</html>"),
    ],
)
def test_body_outside_format_is_value_error(response):
    with pytest.raises(ValueError, match="fora do formato"):
        make(lambda r: response).extract(TEXT, CTX)


@pytest.mark.parametrize("status", [429, 500])
def test_429_and_500_are_unavailable(status):
    with pytest.raises(ProviderUnavailable):
        make(lambda r: httpx.Response(status)).extract(TEXT, CTX)


def test_401_is_config_error():
    with pytest.raises(ProviderConfigError):
        make(lambda r: httpx.Response(401, text="bad token")).extract(TEXT, CTX)


def test_timeout_is_unavailable():
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("slow", request=request)

    with pytest.raises(ProviderUnavailable):
        make(handler).extract(TEXT, CTX)


def test_transcribe_success():
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        seen["auth"] = request.headers["authorization"]
        seen["body"] = json.loads(request.content)
        return httpx.Response(200, json=envelope({"text": "42 de pizza"}))

    assert make(handler).transcribe(AUDIO, "audio/webm;codecs=opus") == "42 de pizza"
    assert seen["url"] == f"{BASE_URL}/accounts/{ACCOUNT}/ai/run/{WHISPER}"
    assert seen["auth"] == f"Bearer {TOKEN}"
    assert seen["body"] == {"audio": base64.b64encode(AUDIO).decode(), "language": "pt"}


def test_transcribe_rejects_bad_audio_without_request():
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        return httpx.Response(200, json=envelope({"text": "x"}))

    g = make(handler)
    with pytest.raises(AudioRejected):
        g.transcribe(AUDIO, "audio/wav")
    with pytest.raises(AudioRejected):
        g.transcribe(b"0" * (4 * 1024 * 1024 + 1), "audio/webm")
    assert calls == []


def test_transcribe_without_whisper_model_is_config_error():
    g = make(lambda r: httpx.Response(200, json=envelope({"text": "x"})), whisper_model=None)
    with pytest.raises(ProviderConfigError):
        g.transcribe(AUDIO, "audio/webm")


def test_transcribe_text_must_be_string():
    g = make(lambda r: httpx.Response(200, json=envelope({"text": 5})))
    with pytest.raises(ValueError, match="fora do formato"):
        g.transcribe(AUDIO, "audio/webm")


def test_repr_and_errors_do_not_leak_secrets():
    g = make(lambda r: httpx.Response(401, text=f"{TOKEN} {TEXT}"))
    assert TOKEN not in repr(g)
    with pytest.raises(ProviderConfigError) as err:
        g.extract(TEXT, CTX)
    assert TOKEN not in str(err.value) and TEXT not in str(err.value)
    bad = make(lambda r: httpx.Response(200, json={"leak": TOKEN, "t": TEXT}))
    with pytest.raises(ValueError) as err2:
        bad.extract(TEXT, CTX)
    assert TOKEN not in str(err2.value) and TEXT not in str(err2.value)


def test_cascade_moves_on_after_429():
    g = make(lambda r: httpx.Response(429))
    name, result = Cascade([("cloudflare", g), ("outro", FakeOk())]).extract(TEXT, CTX)
    assert name == "outro"
    assert result.items[0].description == "outro"


def test_from_env(monkeypatch):
    for name in ("CLOUDFLARE_ACCOUNT_ID", "CLOUDFLARE_API_TOKEN", "CLOUDFLARE_MODEL"):
        monkeypatch.setenv(name, "x")
    monkeypatch.delenv("CLOUDFLARE_WHISPER_MODEL", raising=False)
    assert from_env().whisper_model is None
    monkeypatch.setenv("CLOUDFLARE_WHISPER_MODEL", "")
    assert from_env().whisper_model is None
    monkeypatch.setenv("CLOUDFLARE_WHISPER_MODEL", WHISPER)
    assert from_env().whisper_model == WHISPER
    for name in ("CLOUDFLARE_ACCOUNT_ID", "CLOUDFLARE_API_TOKEN", "CLOUDFLARE_MODEL"):
        monkeypatch.delenv(name)
        with pytest.raises(RuntimeError):
            from_env()
        monkeypatch.setenv(name, "x")


def test_registry_builds_cloudflare(monkeypatch):
    monkeypatch.setenv("CLOUDFLARE_ACCOUNT_ID", ACCOUNT)
    monkeypatch.setenv("CLOUDFLARE_API_TOKEN", TOKEN)
    monkeypatch.setenv("CLOUDFLARE_MODEL", MODEL)
    assert isinstance(registry.provider_registry()["cloudflare"](), CloudflareAI)
