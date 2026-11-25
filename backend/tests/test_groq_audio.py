import httpx
import pytest

from nico.ai.audio import MAX_AUDIO_BYTES, AudioRejected
from nico.ai.base import ProviderConfigError, ProviderUnavailable
from nico.ai.cascade import Cascade
from nico.ai.groq import GroqExtractor, from_env

KEY = "test-key-abc123"
AUDIO = b"fake-audio-bytes"


def make(handler, whisper_model="whisper-teste", calls=None) -> GroqExtractor:
    def wrapped(request: httpx.Request) -> httpx.Response:
        if calls is not None:
            calls.append(request)
        return handler(request)

    client = httpx.Client(transport=httpx.MockTransport(wrapped))
    return GroqExtractor(KEY, "modelo-teste", client=client, whisper_model=whisper_model)


def ok(_request: httpx.Request) -> httpx.Response:
    return httpx.Response(200, json={"text": "quarenta de pizza"})


def test_success_builds_multipart_request():
    calls: list[httpx.Request] = []
    assert make(ok, calls=calls).transcribe(AUDIO, "audio/ogg") == "quarenta de pizza"
    (request,) = calls
    assert str(request.url).endswith("/audio/transcriptions")
    assert request.headers["authorization"] == f"Bearer {KEY}"
    assert request.headers["content-type"].startswith("multipart/form-data")
    body = request.content
    assert b'name="model"\r\n\r\nwhisper-teste' in body
    assert b'name="language"\r\n\r\npt' in body
    assert b'filename="audio.ogg"' in body
    assert b"Content-Type: audio/ogg" in body
    assert AUDIO in body
    assert KEY.encode() not in body


def test_codecs_parameter_accepted():
    calls: list[httpx.Request] = []
    assert make(ok, calls=calls).transcribe(AUDIO, "audio/webm;codecs=opus")
    assert b'filename="audio.webm"' in calls[0].content
    assert b"Content-Type: audio/webm" in calls[0].content


def test_wav_rejected_without_request():
    calls: list[httpx.Request] = []
    with pytest.raises(AudioRejected):
        make(ok, calls=calls).transcribe(AUDIO, "audio/wav")
    assert calls == []


def test_too_big_rejected_without_request():
    calls: list[httpx.Request] = []
    with pytest.raises(AudioRejected):
        make(ok, calls=calls).transcribe(b"x" * (MAX_AUDIO_BYTES + 1), "audio/webm")
    assert calls == []


def test_no_whisper_model_without_request():
    calls: list[httpx.Request] = []
    with pytest.raises(ProviderConfigError):
        make(ok, whisper_model=None, calls=calls).transcribe(AUDIO, "audio/webm")
    assert calls == []


def test_429_is_unavailable():
    with pytest.raises(ProviderUnavailable):
        make(lambda r: httpx.Response(429)).transcribe(AUDIO, "audio/webm")


def test_401_is_config_error():
    with pytest.raises(ProviderConfigError):
        make(lambda r: httpx.Response(401)).transcribe(AUDIO, "audio/webm")


@pytest.mark.parametrize(
    "response",
    [
        httpx.Response(200, json={"other": "x"}),
        httpx.Response(200, json={"text": 5}),
        httpx.Response(200, content=b"not json"),
    ],
)
def test_bad_body_is_value_error(response):
    with pytest.raises(ValueError, match="fora do formato"):
        make(lambda r: response).transcribe(AUDIO, "audio/webm")


def test_via_cascade():
    cascade = Cascade([("groq", make(ok))])
    assert cascade.transcribe(AUDIO, "audio/webm") == ("groq", "quarenta de pizza")


def test_from_env(monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", KEY)
    monkeypatch.setenv("GROQ_MODEL", "modelo-teste")
    monkeypatch.setenv("GROQ_WHISPER_MODEL", "whisper-teste")
    assert from_env().whisper_model == "whisper-teste"
    monkeypatch.delenv("GROQ_WHISPER_MODEL")
    assert from_env().whisper_model is None
    monkeypatch.setenv("GROQ_WHISPER_MODEL", "")
    assert from_env().whisper_model is None
