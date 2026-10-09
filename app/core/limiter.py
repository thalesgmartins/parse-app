"""Configuração de rate limiting para controle de requisições e proteção contra força bruta."""

import os

from fastapi import Request
from slowapi import Limiter


def obter_ip_cliente(request: Request) -> str:
    """Extrai o endereço IP real do cliente considerando Cloudflare e proxies reversos.

    Args:
        request: Requisição HTTP recebida.

    Returns:
        Endereço IP resolvido como string.
    """
    cf_ip = request.headers.get("CF-Connecting-IP")
    if cf_ip:
        return cf_ip.strip()

    x_forwarded = request.headers.get("X-Forwarded-For")
    if x_forwarded:
        return x_forwarded.split(",")[0].strip()

    if request.client and request.client.host:
        return request.client.host

    return "127.0.0.1"


limiter_ativo = os.getenv("TESTING_DISABLE_RATE_LIMIT", "0") != "1"

limiter = Limiter(
    key_func=obter_ip_cliente,
    enabled=limiter_ativo,
    default_limits=[],
)
