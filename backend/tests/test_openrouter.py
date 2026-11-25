import json
from datetime import date

import httpx
import pytest
from pydantic import ValidationError

from nico.ai import registry
from nico.ai.base import ProviderConfigError, ProviderUnavailable
from nico.ai.cascade import Cascade
from nico.ai.openrouter import BASE_URL, OpenRouterExtractor, from_env
from nico.ai.prompt import ExtractionContext
from nico.ai.schema import ExtractedItem, Extraction, Method, Person

KEY = "test-key"
TEXT = "42 de pizza no cartão roxo"
CTX = ExtractionContext(
    today=date(2026, 3, 10),
    methods=[Method("m1", ["roxo"], "credito")],
    people=[Person("p1", ["Ana"])],
)
GOOD = {"items": [{"description": "pizza", "amount_text": "42", "method": "roxo"}]}


def completion(content: str) -> dict:
    return {"choices": [{"message": {"role": "assistant", "content": content}}]}


def make(handler, **kw) -> OpenRouterExtractor:
    """Todo teste passa por aqui: toda requisição precisa levar data_collection=deny."""

    def checked(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        assert body["provider"]["data_collection"] == "deny"
        assert body["provider"]["require_parameters"] is True
        return handler(request)

    client = httpx.Client(transport=httpx.MockTransport(checked))
    return OpenRouterExtractor(KEY, "modelo-teste", client=client, **kw)


def ok(_request: httpx.Request) -> httpx.Response:
    return httpx.Response(200, json=completion(json.dumps(GOOD)))


class FakeOk:
    def extract(self, text, context):
        return Extraction(items=[ExtractedItem(description="outro")])


def test_success_builds_request():
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        seen["auth"] = request.headers["authorization"]
        seen["body"] = json.loads(request.content)
        return ok(request)

    result = make(handler).extract(TEXT, CTX)
    assert result.items[0].description == "pizza"
    assert seen["url"] == f"{BASE_URL}/chat/completions"
    assert seen["auth"] == f"Bearer {KEY}"
    body = seen["body"]
    assert body["model"] == "modelo-teste"
    assert body["temperature"] == 0
    assert body["provider"] == {"data_collection": "deny", "require_parameters": True}
    rf = body["response_format"]
    assert rf["type"] == "json_schema"
    assert rf["json_schema"]["name"] == "extraction"
    assert "$ref" not in json.dumps(rf["json_schema"]["schema"])
    assert [m["role"] for m in body["messages"]] == ["system", "user"]
    assert body["messages"][1]["content"] == TEXT
    assert "roxo" in body["messages"][0]["content"]


def test_429_is_unavailable_and_cascade_moves_on():
    g = make(lambda r: httpx.Response(429, text="slow down"))
    with pytest.raises(ProviderUnavailable):
        g.extract(TEXT, CTX)
    name, result = Cascade([("openrouter", g), ("outro", FakeOk())]).extract(TEXT, CTX)
    assert name == "outro"
    assert result.items[0].description == "outro"


def test_503_is_unavailable_and_cascade_moves_on():
    g = make(lambda r: httpx.Response(503))
    with pytest.raises(ProviderUnavailable):
        g.extract(TEXT, CTX)
    name, _ = Cascade([("openrouter", g), ("outro", FakeOk())]).extract(TEXT, CTX)
    assert name == "outro"


def test_401_is_config_error_and_cascade_raises():
    g = make(lambda r: httpx.Response(401, text="bad key"))
    with pytest.raises(ProviderConfigError):
        g.extract(TEXT, CTX)
    with pytest.raises(ProviderConfigError):
        Cascade([("openrouter", g), ("outro", FakeOk())]).extract(TEXT, CTX)


@pytest.mark.parametrize(
    ("code", "exc"),
    [
        (429, ProviderUnavailable),
        (502, ProviderUnavailable),
        (401, ProviderConfigError),
        (403, ProviderConfigError),
        (400, ValueError),
    ],
)
def test_200_with_error_body(code, exc):
    body = {"error": {"code": code, "message": f"{KEY} {TEXT}"}}
    g = make(lambda r: httpx.Response(200, json=body))
    with pytest.raises(exc) as err:
        g.extract(TEXT, CTX)
    assert KEY not in str(err.value) and TEXT not in str(err.value)


def test_200_with_error_body_cascade():
    g = make(lambda r: httpx.Response(200, json={"error": {"code": 429}}))
    name, _ = Cascade([("openrouter", g), ("outro", FakeOk())]).extract(TEXT, CTX)
    assert name == "outro"
    g = make(lambda r: httpx.Response(200, json={"error": {"code": 401}}))
    with pytest.raises(ProviderConfigError):
        Cascade([("openrouter", g), ("outro", FakeOk())]).extract(TEXT, CTX)


def test_timeout_is_unavailable():
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("slow", request=request)

    with pytest.raises(ProviderUnavailable):
        make(handler).extract(TEXT, CTX)


def test_invalid_json_content_is_validation_error():
    g = make(lambda r: httpx.Response(200, json=completion("isso não é json")))
    with pytest.raises(ValidationError):
        g.extract(TEXT, CTX)


@pytest.mark.parametrize(
    "response",
    [
        httpx.Response(200, json={"id": "x"}),
        httpx.Response(200, json={"choices": []}),
        httpx.Response(200, text="<html>não é json</html>"),
    ],
)
def test_body_without_choices_is_value_error(response):
    with pytest.raises(ValueError, match="fora do formato"):
        make(lambda r: response).extract(TEXT, CTX)


def test_repr_and_errors_do_not_leak_secrets():
    g = make(lambda r: httpx.Response(401, text=f"{KEY} {TEXT}"))
    assert KEY not in repr(g)
    with pytest.raises(ProviderConfigError) as err:
        g.extract(TEXT, CTX)
    assert KEY not in str(err.value) and TEXT not in str(err.value)
    bad = make(lambda r: httpx.Response(200, json={"leak": KEY, "t": TEXT}))
    with pytest.raises(ValueError) as err2:
        bad.extract(TEXT, CTX)
    assert KEY not in str(err2.value) and TEXT not in str(err2.value)


def test_from_env(monkeypatch):
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    monkeypatch.setenv("OPENROUTER_MODEL", "modelo-teste")
    with pytest.raises(RuntimeError):
        from_env()
    monkeypatch.setenv("OPENROUTER_API_KEY", KEY)
    assert isinstance(from_env(), OpenRouterExtractor)
    monkeypatch.delenv("OPENROUTER_MODEL")
    with pytest.raises(RuntimeError):
        from_env()


def test_registry_builds_openrouter(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", KEY)
    monkeypatch.setenv("OPENROUTER_MODEL", "modelo-teste")
    assert isinstance(registry.provider_registry()["openrouter"](), OpenRouterExtractor)
