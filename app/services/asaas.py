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


def _buscar_cobranca_pendente(sub_id: str) -> str | None:
    """Retorna o invoiceUrl da cobrança PENDING ou OVERDUE de uma assinatura."""
    try:
        cobrancas = _requisicao_asaas("GET", f"/subscriptions/{sub_id}/payments")
        lista_pagamentos = cobrancas.get("data")
        if isinstance(lista_pagamentos, list):
            for pgto in lista_pagamentos:
                if isinstance(pgto, dict) and pgto.get("status") in ("PENDING", "OVERDUE"):
                    url_cobranca = pgto.get("invoiceUrl") or pgto.get("bankSlipUrl")
                    if isinstance(url_cobranca, str) and url_cobranca:
                        return url_cobranca
    except ValueError:
        _LOGGER.debug("Não foi possível consultar cobranças da assinatura %s", sub_id)
    return None


def _criar_cobranca_avulsa_asaas(
    customer_id: str,
    valor: float,
    descricao: str,
    ref_externa: str,
    forma_pagamento: str = "UNDEFINED",
) -> str | None:
    """Cria ou reutiliza uma cobrança avulsa (diferença de upgrade ou renovação)."""
    try:
        pendentes = _requisicao_asaas("GET", f"/payments?customer={customer_id}&status=PENDING")
        lista = pendentes.get("data")
        if isinstance(lista, list):
            for pgto in lista:
                if isinstance(pgto, dict) and pgto.get("externalReference") == ref_externa:
                    pid = str(pgto.get("id") or "")
                    if pid:
                        atualizado = _requisicao_asaas(
                            "POST",
                            f"/payments/{pid}",
                            {
                                "billingType": forma_pagamento,
                                "value": valor,
                                "dueDate": (date.today() + timedelta(days=1)).isoformat(),
                                "description": descricao,
                            },
                        )
                        url_ex = atualizado.get("invoiceUrl") or atualizado.get("bankSlipUrl")
                        if isinstance(url_ex, str) and url_ex:
                            return url_ex
    except ValueError:
        pass

    vencimento = (date.today() + timedelta(days=1)).isoformat()
    novo = _requisicao_asaas(
        "POST",
        "/payments",
        {
            "customer": customer_id,
            "billingType": forma_pagamento,
            "value": valor,
            "dueDate": vencimento,
            "description": descricao,
            "externalReference": ref_externa,
        },
    )
    url_nova = novo.get("invoiceUrl") or novo.get("bankSlipUrl")
    return str(url_nova) if isinstance(url_nova, str) and url_nova else None


def listar_pagamentos_confirmados_asaas(
    customer_id: str | None,
    subscription_id: str | None = None,
) -> list[dict[str, object]]:
    """Lista cobranças já confirmadas/recebidas no Asaas para sincronização segura."""
    if not ASAAS_API_KEY.strip():
        return []

    confirmados: list[dict[str, object]] = []
    endpoints: list[str] = []
    if subscription_id and not subscription_id.startswith("sub_local_"):
        endpoints.append(f"/subscriptions/{subscription_id}/payments")
    if customer_id and not customer_id.startswith("cus_local_"):
        endpoints.append(f"/payments?customer={customer_id}&limit=20")

    vistos: set[str] = set()
    for ep in endpoints:
        try:
            resp = _requisicao_asaas("GET", ep)
            dados = resp.get("data")
            if isinstance(dados, list):
                for item in dados:
                    if isinstance(item, dict):
                        pid = str(item.get("id") or "")
                        st = str(item.get("status") or "")
                        if pid and pid not in vistos and st in ("CONFIRMED", "RECEIVED"):
                            vistos.add(pid)
                            confirmados.append(item)
        except ValueError:
            continue
    return confirmados


def criar_assinatura_asaas(
    advogado: Advogado,
    tier: str,
    cpf_cnpj: str | None = None,
    forma_pagamento: str = "UNDEFINED",
    customer_id_atual: str | None = None,
    subscription_id_atual: str | None = None,
    tier_atual: str = "trial",
    ciclo_pago_ativo: bool = False,
) -> ResultadoCheckoutAsaas:
    """Cria ou atualiza assinatura recorrente mensal no Asaas sem cobrança duplicada.

    Regras de proteção financeira:
    - Se a assinatura atual possui fatura PENDING, atualiza a própria fatura pendente.
    - Se o advogado já pagou o mês atual (`ciclo_pago_ativo=True`) e faz UPGRADE:
      atualiza a assinatura recorrente para o próximo mês (`updatePendingPayments=False`)
      e gera cobrança avulsa APENAS da diferença de preço (`novo_valor - valor_atual`).
    - Se o advogado já pagou o mês atual e faz DOWNGRADE:
      agenda o novo valor para o próximo vencimento sem gerar nova cobrança no mês atual.

    Args:
        advogado: Instância do Advogado titular da assinatura.
        tier: Código do plano ('autonomo', 'pequeno_escritorio', 'grande_escritorio').
        cpf_cnpj: CPF ou CNPJ do titular para faturamento no Asaas (opcional).
        forma_pagamento: 'PIX', 'BOLETO', 'CREDIT_CARD' ou 'UNDEFINED'.
        customer_id_atual: ID de cliente Asaas já vinculado ao advogado (opcional).
        subscription_id_atual: ID de assinatura Asaas já existente (opcional).
        tier_atual: Tier atualmente ativo na conta do advogado.
        ciclo_pago_ativo: True se o advogado já está em um ciclo comercial pago vigente.

    Returns:
        ResultadoCheckoutAsaas contendo IDs e URL de pagamento.

    Raises:
        ValueError: Se o plano for inválido ou a chamada à API falhar.
    """
    if tier not in CATALOGO_PLANOS or tier == "trial":
        raise ValueError(f"Plano comercial inválido para assinatura: {tier}")

    plano = CATALOGO_PLANOS[tier]
    plano_anterior = CATALOGO_PLANOS.get(tier_atual, CATALOGO_PLANOS["trial"])

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
    fatura_pendente_url: str | None = None
    if subscription_id_atual and not subscription_id_atual.startswith("sub_local_"):
        fatura_pendente_url = _buscar_cobranca_pendente(subscription_id_atual)
        atualizar_pendentes = fatura_pendente_url is not None or not ciclo_pago_ativo
        try:
            resp_upd = _requisicao_asaas(
                "POST",
                f"/subscriptions/{subscription_id_atual}",
                {
                    "billingType": billing_valido,
                    "value": plano.valor_mensal,
                    "description": descricao_sub,
                    "externalReference": ref_externa,
                    "updatePendingPayments": atualizar_pendentes,
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
        fatura_pendente_url = _buscar_cobranca_pendente(sub_id)

    invoice_url: str | None = fatura_pendente_url
    if not invoice_url and ciclo_pago_ativo and tier_atual != "trial":
        if plano.valor_mensal > plano_anterior.valor_mensal:
            diferenca = round(plano.valor_mensal - plano_anterior.valor_mensal, 2)
            invoice_url = _criar_cobranca_avulsa_asaas(
                customer_id=customer_id,
                valor=diferenca,
                descricao=(
                    f"ParseApp SaaS - Diferença de Upgrade ({plano_anterior.nome} -> {plano.nome})"
                ),
                ref_externa=f"{advogado.id}:{plano.codigo}:upgrade",
                forma_pagamento=billing_valido,
            )
        elif plano.codigo == plano_anterior.codigo:
            invoice_url = _criar_cobranca_avulsa_asaas(
                customer_id=customer_id,
                valor=plano.valor_mensal,
                descricao=f"ParseApp SaaS - Renovação Antecipada ({plano.nome})",
                ref_externa=f"{advogado.id}:{plano.codigo}:renovacao",
                forma_pagamento=billing_valido,
            )

    return ResultadoCheckoutAsaas(
        modo_simulacao=False,
        customer_id=customer_id,
        subscription_id=sub_id,
        checkout_url=invoice_url,
        status_inicial="active" if not invoice_url else "pending_payment",
    )
