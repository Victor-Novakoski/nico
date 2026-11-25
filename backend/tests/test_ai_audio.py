import pytest

from nico.ai.audio import MAX_AUDIO_BYTES, AudioRejected, check_audio


@pytest.mark.parametrize("mime", ["audio/webm", "audio/webm;codecs=opus", "AUDIO/OGG", "audio/mp4"])
def test_accepted_formats(mime):
    assert check_audio(b"x", mime) == mime.split(";")[0].lower()


@pytest.mark.parametrize("mime", ["audio/wav", "video/mp4", ""])
def test_rejected_formats(mime):
    with pytest.raises(AudioRejected):
        check_audio(b"x", mime)


def test_empty_and_too_big():
    with pytest.raises(AudioRejected):
        check_audio(b"", "audio/webm")
    assert check_audio(b"x" * MAX_AUDIO_BYTES, "audio/webm") == "audio/webm"
    with pytest.raises(AudioRejected):
        check_audio(b"x" * (MAX_AUDIO_BYTES + 1), "audio/webm")
