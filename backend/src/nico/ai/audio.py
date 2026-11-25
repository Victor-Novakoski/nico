"""Conferência do áudio antes de mandar para qualquer provedor (decisão 006).

O limite fica abaixo dos 4,5 MB de corpo da Vercel (`docs/LIMITES.md`). A rota de
áudio confere antes da cascata; os provedores conferem de novo por segurança.
"""

from __future__ import annotations

MAX_AUDIO_BYTES = 4 * 1024 * 1024
AUDIO_MIME_TYPES = ("audio/webm", "audio/ogg", "audio/mp4")
EXTENSIONS = {"audio/webm": "webm", "audio/ogg": "ogg", "audio/mp4": "m4a"}


class AudioRejected(ValueError):
    """Áudio vazio, grande demais ou em formato que o app não aceita."""


def base_mime(mime: str) -> str:
    """`audio/webm;codecs=opus` → `audio/webm`."""
    return mime.split(";", 1)[0].strip().lower()


def check_audio(audio: bytes, mime: str) -> str:
    """Devolve o tipo base (sem parâmetros) ou levanta `AudioRejected`."""
    kind = base_mime(mime)
    if kind not in AUDIO_MIME_TYPES:
        raise AudioRejected("formato de áudio não aceito")
    if not audio:
        raise AudioRejected("áudio vazio")
    if len(audio) > MAX_AUDIO_BYTES:
        raise AudioRejected("áudio maior que 4 MB")
    return kind
