"""Erros HTTP dos provedores traduzidos para a cascata (decisão 006).

As mensagens são fixas: nunca levam o corpo da resposta, a frase nem a chave.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import TypeVar

import httpx

from nico.ai.base import ProviderConfigError, ProviderUnavailable

T = TypeVar("T")


def check_response(response: httpx.Response) -> httpx.Response:
    """429 e 5xx passam para o próximo; 401 e 403 levantam; outro 4xx também levanta."""
    status = response.status_code
    if status == 429:
        raise ProviderUnavailable("limite do provedor (429)")
    if status >= 500:
        raise ProviderUnavailable(f"erro do provedor ({status})")
    if status in (401, 403):
        raise ProviderConfigError(f"chave recusada pelo provedor ({status})")
    if status >= 400:
        raise ProviderConfigError(f"pedido recusado pelo provedor ({status})")
    return response


def call(send: Callable[[], httpx.Response]) -> httpx.Response:
    """Faz a chamada e traduz tempo esgotado e falha de conexão em `ProviderUnavailable`."""
    try:
        response = send()
    except httpx.TimeoutException as e:
        raise ProviderUnavailable("tempo esgotado") from e
    except httpx.TransportError as e:
        raise ProviderUnavailable("falha de conexão com o provedor") from e
    return check_response(response)
