"""Cliente de integração com a API REST v3 do Asaas para assinaturas e cobranças."""

import hmac
import json
import logging
import re
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import date, timedelta

from app.core.config import ASAAS_API_KEY, ASAAS_API_URL, ASAAS_WEBHOOK_TOKEN
from app.database.models import Advogado
from app.services.quotas import CATALOGO_PLANOS

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True)
class ResultadoCheckoutAsaas:
    """Dados retornados após solicitar criação/atualização de assinatura."""

    modo_simulacao: bool
    customer_id: str
    subscription_id: str
    checkout_url: str | None
    status_inicial: str


def validar_token_webhook_asaas(token_recebido: str | None) -> bool:
    """Compara em tempo constante o token do cabeçalho asaas-access-token.

    Args:
        token_recebido: Valor do header HTTP 'asaas-access-token'.

    Returns:
        True se o token for idêntico ao segredo configurado no servidor.
    """
    if not token_recebido or not ASAAS_WEBHOOK_TOKEN:
        return False
    return hmac.compare_digest(token_recebido.strip(), ASAAS_WEBHOOK_TOKEN.strip())


def _requisicao_asaas(
    metodo: str,
    endpoint: str,
    payload: dict[str, object] | None = None,
) -> dict[str, object]:
    """Executa requisição HTTP autenticada contra a API v3 do Asaas."""
    url = f"{ASAAS_API_URL.rstrip('/')}/{endpoint.lstrip('/')}"
    corpo = json.dumps(payload).encode("utf-8") if payload is not None else None
    headers = {
        "Content-Type": "application/json",
        "User-Agent": "ParseApp-SaaS/1.0",
        "access_token": ASAAS_API_KEY,
    }
    req = urllib.request.Request(url, data=corpo, headers=headers, method=metodo)
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            dados = json.loads(resp.read().decode("utf-8"))
            return dados if isinstance(dados, dict) else {}
    except urllib.error.HTTPError as err:
        detalhe = err.read().decode("utf-8", errors="ignore")
        _LOGGER.error("Erro HTTP na comunicação com Asaas (%s): %s", err.code, detalhe)
        raise ValueError("Falha ao comunicar com o gateway de pagamentos Asaas.") from err
    except urllib.error.URLError as err:
        _LOGGER.error("Falha de rede ao conectar ao Asaas: %s", err)
        raise ValueError("Gateway de pagamentos Asaas indisponível no momento.") from err


def criar_assinatura_asaas(
    advogado: Advogado,
    tier: str,
    cpf_cnpj: str | None = None,
    forma_pagamento: str = "UNDEFINED",
) -> ResultadoCheckoutAsaas:
    """Cria ou atualiza assinatura recorrente mensal no Asaas (ou em modo local).

    Quando ASAAS_API_KEY não está configurada no ambiente, opera em modo de
    homologação local ativando o tier imediatamente. Quando configurada, cria
    o customer e a subscription no Asaas v3 e retorna o link de pagamento.

    Args:
        advogado: Instância do Advogado titular da assinatura.
        tier: Código do plano ('autonomo', 'pequeno_escritorio', 'grande_escritorio').
        cpf_cnpj: CPF ou CNPJ do titular para faturamento no Asaas (opcional).
        forma_pagamento: 'PIX', 'BOLETO', 'CREDIT_CARD' ou 'UNDEFINED'.

    Returns:
        ResultadoCheckoutAsaas contendo IDs e URL de pagamento.

    Raises:
        ValueError: Se o plano for inválido ou a chamada à API falhar.
    """
    if tier not in CATALOGO_PLANOS or tier == "trial":
        raise ValueError(f"Plano comercial inválido para assinatura: {tier}")

    plano = CATALOGO_PLANOS[tier]

    if not ASAAS_API_KEY.strip():
        return ResultadoCheckoutAsaas(
            modo_simulacao=True,
            customer_id=f"cus_local_{advogado.id.hex[:12]}",
            subscription_id=f"sub_local_{tier}_{advogado.id.hex[:8]}",
            checkout_url=None,
            status_inicial="active",
        )

    doc_limpo = re.sub(r"\D", "", cpf_cnpj or "")
    payload_cliente: dict[str, object] = {
        "name": advogado.nome,
        "email": advogado.email,
        "externalReference": str(advogado.id),
    }
    if doc_limpo:
        payload_cliente["cpfCnpj"] = doc_limpo

    resp_cliente = _requisicao_asaas("POST", "/customers", payload_cliente)
    customer_id = str(resp_cliente.get("id", ""))
    if not customer_id:
        raise ValueError("Asaas não retornou o identificador do cliente (customer_id).")

    vencimento = (date.today() + timedelta(days=1)).isoformat()
    billing_valido = (
        forma_pagamento
        if forma_pagamento in ("PIX", "BOLETO", "CREDIT_CARD", "UNDEFINED")
        else "UNDEFINED"
    )
    payload_sub: dict[str, object] = {
        "customer": customer_id,
        "billingType": billing_valido,
        "value": plano.valor_mensal,
        "nextDueDate": vencimento,
        "cycle": "MONTHLY",
        "description": f"ParseApp SaaS - Plano {plano.nome} ({plano.limite_mensal} extratos/mês)",
        "externalReference": f"{advogado.id}:{plano.codigo}",
    }
    resp_sub = _requisicao_asaas("POST", "/subscriptions", payload_sub)
    sub_id = str(resp_sub.get("id", ""))
    if not sub_id:
        raise ValueError("Asaas não retornou o identificador da assinatura (subscription_id).")

    invoice_url: str | None = None
    try:
        cobrancas = _requisicao_asaas("GET", f"/subscriptions/{sub_id}/payments")
        lista_pagamentos = cobrancas.get("data")
        if isinstance(lista_pagamentos, list) and lista_pagamentos:
            primeiro = lista_pagamentos[0]
            if isinstance(primeiro, dict):
                url_cobranca = primeiro.get("invoiceUrl") or primeiro.get("bankSlipUrl")
                if isinstance(url_cobranca, str) and url_cobranca:
                    invoice_url = url_cobranca
    except ValueError:
        _LOGGER.debug("Link direto da cobrança ainda não disponível para sub %s", sub_id)

    return ResultadoCheckoutAsaas(
        modo_simulacao=False,
        customer_id=customer_id,
        subscription_id=sub_id,
        checkout_url=invoice_url,
        status_inicial="active",
    )
