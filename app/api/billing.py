"""Rotas de gerenciamento de Planos (Tiers) e Webhook de pagamentos do Asaas."""

import logging
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Form, Header, HTTPException, Request
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.auth import obter_usuario_logado
from app.database.models import Advogado, Assinatura, EventoPagamento
from app.database.session import get_db
from app.services.asaas import criar_assinatura_asaas, validar_token_webhook_asaas
from app.services.quotas import (
    CATALOGO_PLANOS,
    atualizar_plano_assinatura,
    obter_resumo_quota,
)

_LOGGER = logging.getLogger(__name__)
router = APIRouter(prefix="/assinaturas", tags=["Planos e Assinaturas"])


@router.get("/meu-plano")
async def consultar_meu_plano(
    usuario: Annotated[Advogado, Depends(obter_usuario_logado)],
    db: Annotated[Session, Depends(get_db)],
) -> dict[str, object]:
    """Retorna o resumo JSON do plano, franquia mensal e consumo atual do advogado."""
    resumo = obter_resumo_quota(db, usuario.id)
    return {
        "tier": resumo.tier,
        "nome_plano": resumo.nome_plano,
        "status": resumo.status,
        "limite_mensal": resumo.limite_mensal,
        "creditos_consumidos": resumo.creditos_consumidos,
        "creditos_reservados": resumo.creditos_reservados,
        "creditos_restantes": resumo.creditos_restantes,
        "percentual_uso": resumo.percentual_uso,
        "valor_mensal": resumo.valor_mensal,
        "checkout_url": resumo.checkout_url,
    }


@router.post("/assinar")
async def assinar_plano_tier(
    tier: Annotated[str, Form()],
    usuario: Annotated[Advogado, Depends(obter_usuario_logado)],
    db: Annotated[Session, Depends(get_db)],
    cpf_cnpj: Annotated[str | None, Form()] = None,
    forma_pagamento: Annotated[str, Form()] = "UNDEFINED",
) -> RedirectResponse:
    """Inicia ou atualiza a assinatura do advogado em um dos 3 tiers comerciais.

    Args:
        tier: Código do plano ('autonomo', 'pequeno_escritorio', 'grande_escritorio').
        usuario: Advogado autenticado.
        db: Sessão ativa do banco de dados.
        cpf_cnpj: CPF ou CNPJ do assinante para emissão no Asaas (opcional).
        forma_pagamento: Modalidade preferencial ('PIX', 'CREDIT_CARD', 'BOLETO').

    Returns:
        Redirecionamento para o checkout do Asaas ou para o dashboard atualizado.
    """
    if tier not in CATALOGO_PLANOS or tier == "trial":
        return RedirectResponse(
            url="/dashboard?erro_plano=Plano+selecionado+inválido.",
            status_code=303,
        )

    try:
        resultado = criar_assinatura_asaas(
            advogado=usuario,
            tier=tier,
            cpf_cnpj=cpf_cnpj,
            forma_pagamento=forma_pagamento,
        )
        atualizar_plano_assinatura(
            db=db,
            advogado_id=usuario.id,
            tier=tier,
            asaas_customer_id=resultado.customer_id,
            asaas_subscription_id=resultado.subscription_id,
            checkout_url=resultado.checkout_url,
            status=resultado.status_inicial,
            reiniciar_ciclo=True,
        )
        if resultado.checkout_url and not resultado.modo_simulacao:
            return RedirectResponse(url=resultado.checkout_url, status_code=303)

        plano_nome = CATALOGO_PLANOS[tier].nome
        return RedirectResponse(
            url=f"/dashboard?sucesso_plano=Plano+{plano_nome}+ativado+com+sucesso!",
            status_code=303,
        )
    except ValueError as exc:
        _LOGGER.error("Erro ao processar assinatura para %s: %s", usuario.email, exc)
        return RedirectResponse(
            url=f"/dashboard?erro_plano={str(exc)}",
            status_code=303,
        )


def _resolver_assinatura_webhook(
    db: Session,
    subscription_id: str | None,
    external_ref: str | None,
) -> tuple[Assinatura | None, str | None]:
    """Localiza a assinatura correspondente ao evento enviado pelo Asaas."""
    tier_extraido: str | None = None
    if external_ref and ":" in external_ref:
        partes = external_ref.split(":", 1)
        try:
            adv_uuid = uuid.UUID(partes[0])
            tier_candidato = partes[1].strip()
            if tier_candidato in CATALOGO_PLANOS:
                tier_extraido = tier_candidato
            sub = db.scalar(select(Assinatura).where(Assinatura.advogado_id == adv_uuid))
            if sub:
                return sub, tier_extraido
        except ValueError:
            pass

    if subscription_id:
        sub = db.scalar(
            select(Assinatura).where(Assinatura.asaas_subscription_id == subscription_id)
        )
        if sub:
            return sub, tier_extraido

    return None, tier_extraido


@router.post("/webhook/asaas")
async def receber_webhook_asaas(
    request: Request,
    db: Annotated[Session, Depends(get_db)],
    asaas_access_token: Annotated[str | None, Header(alias="asaas-access-token")] = None,
) -> dict[str, str]:
    """Processa notificações de cobrança do Asaas com garantia de idempotência.

    Args:
        request: Requisição HTTP contendo o JSON do evento Asaas.
        db: Sessão ativa do banco de dados.
        asaas_access_token: Token secreto enviado pelo Asaas no header HTTP.

    Returns:
        Dicionário confirmando o recebimento ou descartando evento duplicado.

    Raises:
        HTTPException: 401 caso o token de autenticação do webhook seja inválido.
    """
    if not validar_token_webhook_asaas(asaas_access_token):
        raise HTTPException(status_code=401, detail="Token de webhook Asaas inválido.")

    corpo = await request.json()
    if not isinstance(corpo, dict):
        raise HTTPException(status_code=400, detail="Payload de webhook inválido.")

    event_id = str(corpo.get("id") or "").strip()
    tipo_evento = str(corpo.get("event") or "").strip()
    payment = corpo.get("payment") if isinstance(corpo.get("payment"), dict) else {}
    payment_id = str(payment.get("id") or "") if isinstance(payment, dict) else ""
    subscription_id = str(payment.get("subscription") or "") if isinstance(payment, dict) else ""
    external_ref = str(payment.get("externalReference") or "") if isinstance(payment, dict) else ""

    if not event_id or not tipo_evento:
        raise HTTPException(status_code=400, detail="Campos obrigatórios ausentes no evento.")

    ja_processado = db.scalar(select(EventoPagamento).where(EventoPagamento.event_id == event_id))
    if ja_processado:
        return {"status": "ignored_duplicate", "event_id": event_id}

    status_pagamento = str(payment.get("status") or "") if isinstance(payment, dict) else ""
    registro_evento = EventoPagamento(
        event_id=event_id,
        asaas_payment_id=payment_id or None,
        asaas_subscription_id=subscription_id or None,
        tipo_evento=tipo_evento,
        payload_resumo=f"ref={external_ref} status={status_pagamento}",
    )
    db.add(registro_evento)

    assinatura, tier_ref = _resolver_assinatura_webhook(db, subscription_id, external_ref)
    if assinatura:
        tier_alvo = tier_ref or assinatura.tier
        if tipo_evento in ("PAYMENT_CONFIRMED", "PAYMENT_RECEIVED"):
            atualizar_plano_assinatura(
                db=db,
                advogado_id=assinatura.advogado_id,
                tier=tier_alvo if tier_alvo in CATALOGO_PLANOS else assinatura.tier,
                asaas_subscription_id=subscription_id or assinatura.asaas_subscription_id,
                status="active",
                reiniciar_ciclo=True,
            )
        elif tipo_evento == "PAYMENT_OVERDUE":
            assinatura.status = "past_due"
        elif tipo_evento in ("SUBSCRIPTION_DELETED", "SUBSCRIPTION_INACTIVATED"):
            assinatura.status = "canceled"

    db.commit()
    return {"status": "processed", "event_id": event_id, "event": tipo_evento}
