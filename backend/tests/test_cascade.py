import pytest

from nico.ai.base import (
    AllProvidersFailed,
    Extractor,
    ProviderConfigError,
    ProviderUnavailable,
    Transcriber,
)
from nico.ai.cascade import Cascade, build_cascade
from nico.ai.schema import ExtractedItem, Extraction

GOOD = Extraction(items=[ExtractedItem(description="pao", amount_text="15")])


class Fake:
    """Provedor falso: devolve `result` ou levanta `result` se for exceção."""

    def __init__(self, result):
        self.result = result
        self.calls = 0

    def _go(self):
        self.calls += 1
        if isinstance(self.result, BaseException):
            raise self.result
        return self.result

    def extract(self, text, context):
        return self._go()

    def transcribe(self, audio, mime):
        return self._go()


def invalid():
    try:
        Extraction.model_validate({"items": "nao e lista"})
    except Exception as e:  # ValidationError
        return e


def test_first_answers():
    a, b = Fake(GOOD), Fake(GOOD)
    assert Cascade([("a", a), ("b", b)]).extract("x", None) == ("a", GOOD)
    assert b.calls == 0


@pytest.mark.parametrize(
    "error", [ProviderUnavailable("429"), ProviderUnavailable("503"), TimeoutError(), invalid()]
)
def test_falls_through_to_next(error):
    a, b = Fake(error), Fake(GOOD)
    assert Cascade([("a", a), ("b", b)]).extract("x", None) == ("b", GOOD)
    assert (a.calls, b.calls) == (1, 1)


def test_wrong_type_is_invalid_response():
    assert Cascade([("a", Fake({"items": []})), ("b", Fake(GOOD))]).extract("x", None)[0] == "b"


def test_config_error_raises_without_calling_next():
    a, b = Fake(ProviderConfigError("401")), Fake(GOOD)
    with pytest.raises(ProviderConfigError):
        Cascade([("a", a), ("b", b)]).extract("x", None)
    assert b.calls == 0


def test_all_fail_reports_names_and_reasons_without_text():
    secret = "gastei 999 no mercado"
    c = Cascade([("a", Fake(ProviderUnavailable("x"))), ("b", Fake(TimeoutError()))])
    with pytest.raises(AllProvidersFailed) as e:
        c.extract(secret, None)
    assert e.value.names == ["a", "b"]
    assert secret not in str(e.value) and "999" not in str(e.value)


def test_empty_list():
    with pytest.raises(AllProvidersFailed) as e:
        Cascade([]).extract("x", None)
    assert e.value.names == []


def test_skips_provider_without_the_capability():
    class OnlyExtract:
        def extract(self, text, context):
            return GOOD

    assert Cascade([("e", OnlyExtract())]).extract("x", None)[0] == "e"
    with pytest.raises(AllProvidersFailed):
        Cascade([("e", OnlyExtract())]).transcribe(b"", "audio/webm")


def test_transcribe_same_logic():
    a, b = Fake(ProviderUnavailable("429")), Fake("ola")
    assert Cascade([("a", a), ("b", b)]).transcribe(b"1", "audio/webm") == ("b", "ola")
    with pytest.raises(ProviderConfigError):
        Cascade([("a", Fake(ProviderConfigError("401"))), ("b", b)]).transcribe(b"1", "x")
    with pytest.raises(AllProvidersFailed):
        Cascade([("a", Fake("  "))]).transcribe(b"1", "x")


def test_protocols():
    assert isinstance(Fake(GOOD), Extractor) and isinstance(Fake("t"), Transcriber)


def test_build_cascade_orders_and_rejects_unknown():
    registry = {"groq": lambda: Fake(GOOD), "cloudflare": lambda: Fake(GOOD)}
    c = build_cascade("cloudflare, groq", registry)
    assert [n for n, _ in c.providers] == ["cloudflare", "groq"]
    assert build_cascade("", registry).providers == []
    with pytest.raises(ValueError, match="desconhecido.*foo"):
        build_cascade("groq,foo", registry)
