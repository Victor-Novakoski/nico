from datetime import date

import pytest

from nico.ai.base import ProviderUnavailable
from nico.ai.cascade import Cascade
from nico.routes.drafts import get_cascade

URL = "/api/drafts/audio"
TODAY = date(2026, 11, 25)
WEBM = "audio/webm;codecs=opus"


class FakeTranscriber:
    def __init__(self, result):
        self.result = result
        self.calls = []

    def transcribe(self, audio, mime):
        self.calls.append((len(audio), mime))
        if isinstance(self.result, BaseException):
            raise self.result
        return self.result


@pytest.fixture(autouse=True)
def _fixed_today(monkeypatch):
    monkeypatch.setattr("nico.routes.drafts.dates.today_sp", lambda: TODAY)


@pytest.fixture
def use_audio(logged_client):
    from nico.app import app

    def install(result):
        provider = FakeTranscriber(result)
        app.dependency_overrides[get_cascade] = lambda: Cascade([("fake", provider)])
        return provider

    yield install
    app.dependency_overrides.pop(get_cascade, None)


def upload(client, data=b"abc", mime=WEBM):
    return client.post(URL, files={"file": ("gasto.webm", data, mime)})


def set_ai(client, enabled=True):
    assert client.patch("/api/me/settings", json={"ai_enabled": enabled}).status_code == 200


def test_audio_becomes_drafts_and_transcript(logged_client, use_audio):
    provider = use_audio("15 pão")
    set_ai(logged_client)
    response = upload(logged_client)
    assert response.status_code == 200
    body = response.json()
    assert body["transcript"] == "15 pão"
    assert body["understood"] is True
    assert body["origin"] == "rules"
    assert [d["amount_cents"] for d in body["drafts"]] == [1500]
    assert provider.calls == [(3, "audio/webm")]


def test_file_over_4mb_is_413(logged_client, use_audio):
    provider = use_audio("15 pão")
    set_ai(logged_client)
    response = upload(logged_client, b"x" * (4 * 1024 * 1024 + 1))
    assert response.status_code == 413
    assert "4 MB" in response.json()["detail"]
    assert provider.calls == []


def test_invalid_mime_is_rejected(logged_client, use_audio):
    provider = use_audio("15 pão")
    set_ai(logged_client)
    response = upload(logged_client, mime="text/plain")
    assert response.status_code == 422
    assert "Formato" in response.json()["detail"]
    assert provider.calls == []


def test_requires_login(client):
    response = client.post(URL, files={"file": ("a.webm", b"abc", "audio/webm")})
    assert response.status_code == 401


def test_all_providers_failing_falls_back_to_form(logged_client, use_audio):
    use_audio(ProviderUnavailable("limite"))
    set_ai(logged_client)
    response = upload(logged_client)
    assert response.status_code == 200
    body = response.json()
    assert body["fallback"] == "form"
    assert body["drafts"] == []
    assert body["transcript"] is None


def test_ai_off_falls_back_to_form(logged_client, use_audio):
    provider = use_audio("15 pão")
    set_ai(logged_client, False)
    response = upload(logged_client)
    assert response.json()["fallback"] == "form"
    assert provider.calls == []
