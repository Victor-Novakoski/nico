import httpx
import pytest

from nico.ai import registry
from nico.ai.base import ProviderConfigError, ProviderUnavailable
from nico.ai.cascade import build_cascade
from nico.ai.http import call, check_response


def resp(status: int) -> httpx.Response:
    return httpx.Response(status, request=httpx.Request("POST", "https://example.test"))


@pytest.mark.parametrize("status", [429, 500, 502, 503])
def test_retryable_status(status):
    with pytest.raises(ProviderUnavailable):
        check_response(resp(status))


@pytest.mark.parametrize("status", [400, 401, 403, 404])
def test_config_status(status):
    with pytest.raises(ProviderConfigError):
        check_response(resp(status))


def test_ok_passes():
    assert check_response(resp(200)).status_code == 200


def test_timeout_and_connection_error():
    def timeout():
        raise httpx.ReadTimeout("lento")

    def refused():
        raise httpx.ConnectError("recusado")

    with pytest.raises(ProviderUnavailable):
        call(timeout)
    with pytest.raises(ProviderUnavailable):
        call(refused)


def test_registry_is_lazy(monkeypatch):
    built = []

    class FakeModule:
        @staticmethod
        def from_env():
            built.append("x")
            return object()

    monkeypatch.setattr(registry.importlib, "import_module", lambda name: FakeModule)
    reg = registry.provider_registry()
    assert set(reg) == {"groq", "cloudflare", "openrouter", "ollama"}
    cascade = build_cascade("ollama", reg)
    assert [n for n, _ in cascade.providers] == ["ollama"]
    assert built == ["x"]
