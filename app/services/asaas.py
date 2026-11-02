"""Cliente de integração com a API REST v3 do Asaas para assinaturas e cobranças."""

import hmac
import json
import logging
import re
import urllib.error
import urllib.parse
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
        mensagem_asaas = "Falha ao comunicar com o gateway de pagamentos Asaas."
        try:
            erro_json = json.loads(detalhe)
            if isinstance(erro_json, dict) and isinstance(erro_json.get("errors"), list):
                lista_erros = erro_json["errors"]
                if lista_erros and isinstance(lista_erros[0], dict):
                    desc = str(lista_erros[0].get("description") or "").strip()
                    if desc:
                        mensagem_asaas = f"Asaas: {desc}"
        except ValueError:
            pass
        raise ValueError(mensagem_asaas) from err
    except urllib.error.URLError as err:
        _LOGGER.error("Falha de rede ao conectar ao Asaas: %s", err)
        raise ValueError("Gateway de pagamentos Asaas indisponível no momento.") from err


def _obter_ou_criar_cliente_asaas(
    advogado: Advogado,
    doc_limpo: str,
    customer_id_atual: str | None = None,
) -> str:
    """Reutiliza o cliente já existente no Asaas ou cria um único cadastro."""
    payload_cliente: dict[str, object] = {
        "name": advogado.nome,
        "email": advogado.email,
        "cpfCnpj": doc_limpo,
        "externalReference": str(advogado.id),
    }

    if customer_id_atual and not customer_id_atual.startswith("cus_local_"):
        try:
            _requisicao_asaas("POST", f"/customers/{customer_id_atual}", payload_cliente)
            return customer_id_atual
        except ValueError:
            _LOGGER.debug(
                "Cliente %s não encontrado no Asaas; buscando por e-mail.", customer_id_atual
            )

    try:
        email_q = urllib.parse.quote(advogado.email)
        busca = _requisicao_asaas("GET", f"/customers?email={email_q}")
        lista = busca.get("data")
        if isinstance(lista, list) and lista:
            for item in lista:
                if isinstance(item, dict) and not item.get("deleted") and item.get("id"):
                    cid_encontrado = str(item["id"])
                    if not item.get("cpfCnpj"):
                        _requisicao_asaas("POST", f"/customers/{cid_encontrado}", payload_cliente)
                    return cid_encontrado
    except ValueError:
        pass

    resp_cliente = _requisicao_asaas("POST", "/customers", payload_cliente)
    customer_id = str(resp_cliente.get("id", ""))
    if not customer_id:
        raise ValueError("Asaas não retornou o identificador do cliente (customer_id).")
    return customer_id


def criar_assinatura_asaas(
    advogado: Advogado,
    tier: str,
    cpf_cnpj: str | None = None,
    forma_pagamento: str = "UNDEFINED",
    customer_id_atual: str | None = None,
    subscription_id_atual: str | None = None,
) -> ResultadoCheckoutAsaas:
    """Cria ou atualiza assinatura recorrente mensal no Asaas (ou em modo local).

    Quando ASAAS_API_KEY não está configurada no ambiente, opera em modo de
    homologação local ativando o tier imediatamente. Quando configurada,
    reutiliza ou cria o customer e a subscription no Asaas v3.

    Args:
        advogado: Instância do Advogado titular da assinatura.
        tier: Código do plano ('autonomo', 'pequeno_escritorio', 'grande_escritorio').
        cpf_cnpj: CPF ou CNPJ do titular para faturamento no Asaas (opcional).
        forma_pagamento: 'PIX', 'BOLETO', 'CREDIT_CARD' ou 'UNDEFINED'.
        customer_id_atual: ID de cliente Asaas já vinculado ao advogado (opcional).
        subscription_id_atual: ID de assinatura Asaas já existente (opcional).

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
            customer_id=customer_id_atual or f"cus_local_{advogado.id.hex[:12]}",
            subscription_id=subscription_id_atual or f"sub_local_{tier}_{advogado.id.hex[:8]}",
            checkout_url=None,
            status_inicial="active",
        )

    doc_origem = cpf_cnpj or getattr(advogado, "cpf_cnpj", None) or ""
    doc_limpo = re.sub(r"\D", "", doc_origem)
    eh_sandbox_asaas = (
        "sandbox.asaas.com" in ASAAS_API_URL.lower()
        or ASAAS_API_KEY.strip().startswith("$aact_hmlg_")
    )
    if not doc_limpo and eh_sandbox_asaas:
        doc_limpo = "24971563792"
    elif len(doc_limpo) not in (11, 14):
        raise ValueError(
            "Para assinar, preencha seu CPF ou CNPJ nas Configurações do Perfil (menu lateral)."
        )

    customer_id = _obter_ou_criar_cliente_asaas(
        advogado=advogado,
        doc_limpo=doc_limpo,
        customer_id_atual=customer_id_atual,
    )

    vencimento = (date.today() + timedelta(days=1)).isoformat()
    billing_valido = (
        forma_pagamento
        if forma_pagamento in ("PIX", "BOLETO", "CREDIT_CARD", "UNDEFINED")
        else "UNDEFINED"
    )
    descricao_sub = f"ParseApp SaaS - Plano {plano.nome} ({plano.limite_mensal} extratos/mês)"
    ref_externa = f"{advogado.id}:{plano.codigo}"

    sub_id = ""
    if subscription_id_atual and not subscription_id_atual.startswith("sub_local_"):
        try:
            resp_upd = _requisicao_asaas(
                "POST",
                f"/subscriptions/{subscription_id_atual}",
                {
                    "billingType": billing_valido,
                    "value": plano.valor_mensal,
                    "description": descricao_sub,
                    "externalReference": ref_externa,
                    "updatePendingPayments": True,
                },
            )
            sub_id = str(resp_upd.get("id", ""))
        except ValueError:
            sub_id = ""

    if not sub_id:
        payload_sub: dict[str, object] = {
            "customer": customer_id,
            "billingType": billing_valido,
            "value": plano.valor_mensal,
            "nextDueDate": vencimento,
            "cycle": "MONTHLY",
            "description": descricao_sub,
            "externalReference": ref_externa,
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
