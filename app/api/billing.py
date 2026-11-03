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
from app.services.asaas import (
    criar_assinatura_asaas,
    listar_pagamentos_confirmados_asaas,
    validar_token_webhook_asaas,
)
from app.services.quotas import (
    CATALOGO_PLANOS,
    _ciclo_mensal_expirado,
    atualizar_plano_assinatura,
    cancelar_assinatura_advogado,
    garantir_assinatura_advogado,
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

    assinatura_atual = garantir_assinatura_advogado(db, usuario.id)
    em_uso = assinatura_atual.creditos_consumidos + assinatura_atual.creditos_reservados
    ciclo_pago_ativo = (
        assinatura_atual.tier != "trial"
        and assinatura_atual.status == "active"
        and em_uso < assinatura_atual.limite_mensal
    )
    if assinatura_atual.tier == tier and ciclo_pago_ativo:
        return RedirectResponse(
            url=(
                "/dashboard?sucesso_plano=Este+já+é+o+seu+plano+ativo+"
                "(a+renovação+mensal+é+automática)."
            ),
            status_code=303,
        )

    if cpf_cnpj and cpf_cnpj.strip():
        digitos = "".join(ch for ch in cpf_cnpj if ch.isdigit())
        if len(digitos) in (11, 14):
            usuario.cpf_cnpj = digitos
            db.commit()

    deve_reiniciar_ciclo = (
        assinatura_atual.tier == "trial" or em_uso >= assinatura_atual.limite_mensal
    )

    try:
        resultado = criar_assinatura_asaas(
            advogado=usuario,
            tier=tier,
            cpf_cnpj=cpf_cnpj or usuario.cpf_cnpj,
            forma_pagamento=forma_pagamento,
            customer_id_atual=assinatura_atual.asaas_customer_id,
            subscription_id_atual=assinatura_atual.asaas_subscription_id,
            tier_atual=assinatura_atual.tier,
            ciclo_pago_ativo=ciclo_pago_ativo,
        )
        if resultado.modo_simulacao:
            atualizar_plano_assinatura(
                db=db,
                advogado_id=usuario.id,
                tier=tier,
                asaas_customer_id=resultado.customer_id,
                asaas_subscription_id=resultado.subscription_id,
                checkout_url=None,
                status="active",
                reiniciar_ciclo=deve_reiniciar_ciclo,
            )
            plano_nome = CATALOGO_PLANOS[tier].nome
            return RedirectResponse(
                url=f"/dashboard?sucesso_plano=Plano+{plano_nome}+ativado+com+sucesso!",
                status_code=303,
            )

        assinatura_atual.asaas_customer_id = resultado.customer_id
        assinatura_atual.asaas_subscription_id = resultado.subscription_id
        assinatura_atual.checkout_url = resultado.checkout_url
        db.commit()

        if resultado.checkout_url:
            return RedirectResponse(url=resultado.checkout_url, status_code=303)

        plano_nome = CATALOGO_PLANOS[tier].nome
        return RedirectResponse(
            url=(
                f"/dashboard?sucesso_plano=Plano+{plano_nome}+agendado+para+o+"
                f"próximo+ciclo+mensal+(sem+cobrança+adicional+neste+mês)!"
            ),
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
) -> tuple[Assinatura | None, str | None, str]:
    """Localiza a assinatura, o tier e o modo ('upgrade'/'renovacao'/'') do evento."""
    tier_extraido: str | None = None
    modo_operacao: str = ""
    if external_ref and ":" in external_ref:
        partes = external_ref.split(":")
        try:
            adv_uuid = uuid.UUID(partes[0])
            tier_candidato = partes[1].strip()
            if tier_candidato in CATALOGO_PLANOS:
                tier_extraido = tier_candidato
            if len(partes) > 2:
                modo_operacao = partes[2].strip().lower()
            sub = db.scalar(select(Assinatura).where(Assinatura.advogado_id == adv_uuid))
            if sub:
                return sub, tier_extraido, modo_operacao
        except ValueError:
            pass

    if subscription_id:
        sub = db.scalar(
            select(Assinatura).where(Assinatura.asaas_subscription_id == subscription_id)
        )
        if sub:
            return sub, tier_extraido, modo_operacao

    return None, tier_extraido, modo_operacao


def _pagamento_ja_confirmado(db: Session, payment_id: str) -> bool:
    """Verifica se um payment_id do Asaas já liberou créditos anteriormente."""
    if not payment_id:
        return False
    stmt = select(EventoPagamento).where(
        EventoPagamento.asaas_payment_id == payment_id,
        EventoPagamento.tipo_evento.in_(
            ("PAYMENT_CONFIRMED", "PAYMENT_RECEIVED", "SYNC_CONFIRMED")
        ),
    )
    return db.scalar(stmt) is not None


def sincronizar_assinatura_com_asaas(db: Session, advogado_id: uuid.UUID) -> bool:
    """Consulta o Asaas para ativar/renovar planos cujas faturas já foram pagas.

    Garante que o cliente receba os créditos mesmo se o webhook atrasar, sem
    jamais aplicar o mesmo pagamento duas vezes.
    """
    assinatura = garantir_assinatura_advogado(db, advogado_id)
    if not assinatura.asaas_customer_id and not assinatura.asaas_subscription_id:
        return False

    confirmados = listar_pagamentos_confirmados_asaas(
        customer_id=assinatura.asaas_customer_id,
        subscription_id=assinatura.asaas_subscription_id,
    )
    ativou_algum = False
    for pgto in confirmados:
        payment_id = str(pgto.get("id") or "").strip()
        if not payment_id or _pagamento_ja_confirmado(db, payment_id):
            continue

        subscription_id = str(pgto.get("subscription") or "").strip()
        external_ref = str(pgto.get("externalReference") or "").strip()
        status_pgto = str(pgto.get("status") or "").strip()

        _, tier_ref, modo_op = _resolver_assinatura_webhook(db, subscription_id, external_ref)
        tier_alvo = tier_ref if (tier_ref and tier_ref in CATALOGO_PLANOS) else assinatura.tier
        if tier_alvo == "trial":
            continue

        db.add(
            EventoPagamento(
                event_id=f"sync_{payment_id}",
                asaas_payment_id=payment_id,
                asaas_subscription_id=subscription_id or None,
                tipo_evento="SYNC_CONFIRMED",
                payload_resumo=f"ref={external_ref} status={status_pgto}",
            )
        )
        reiniciar = modo_op != "upgrade"
        atualizar_plano_assinatura(
            db=db,
            advogado_id=assinatura.advogado_id,
            tier=tier_alvo,
            asaas_subscription_id=subscription_id or assinatura.asaas_subscription_id,
            checkout_url="",
            status="active",
            reiniciar_ciclo=reiniciar,
        )
        ativou_algum = True

    if ativou_algum:
        assinatura_ref = garantir_assinatura_advogado(db, advogado_id)
        assinatura_ref.checkout_url = None
        db.commit()
    return ativou_algum


@router.post("/sincronizar")
async def rota_sincronizar_assinatura(
    usuario: Annotated[Advogado, Depends(obter_usuario_logado)],
    db: Annotated[Session, Depends(get_db)],
) -> RedirectResponse:
    """Verifica manualmente no Asaas se a fatura pendente já foi paga."""
    ativou = sincronizar_assinatura_com_asaas(db, usuario.id)
    if ativou:
        return RedirectResponse(
            url="/dashboard?sucesso_plano=Pagamento+confirmado+e+franquia+atualizada!",
            status_code=303,
        )
    return RedirectResponse(
        url="/dashboard?erro_plano=O+pagamento+ainda+aguarda+confirmação+da+compensação.",
        status_code=303,
    )


@router.post("/cancelar")
async def cancelar_minha_assinatura(
    usuario: Annotated[Advogado, Depends(obter_usuario_logado)],
    db: Annotated[Session, Depends(get_db)],
) -> RedirectResponse:
    """Cancela a renovação da assinatura mantendo o acesso até o fim do ciclo."""
    cancelar_assinatura_advogado(db, usuario.id)
    return RedirectResponse(
        url=(
            "/dashboard?sucesso_plano=Renovação+automática+cancelada!+"
            "Você+continuará+com+acesso+aos+seus+extratos+até+o+fim+do+ciclo+atual."
        ),
        status_code=303,
    )


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

    pagamento_ja_ativado = tipo_evento in (
        "PAYMENT_CONFIRMED",
        "PAYMENT_RECEIVED",
    ) and _pagamento_ja_confirmado(db, payment_id)

    status_pagamento = str(payment.get("status") or "") if isinstance(payment, dict) else ""
    registro_evento = EventoPagamento(
        event_id=event_id,
        asaas_payment_id=payment_id or None,
        asaas_subscription_id=subscription_id or None,
        tipo_evento=tipo_evento,
        payload_resumo=f"ref={external_ref} status={status_pagamento}",
    )
    db.add(registro_evento)

    assinatura, tier_ref, modo_op = _resolver_assinatura_webhook(db, subscription_id, external_ref)
    if assinatura:
        tier_alvo = tier_ref or assinatura.tier
        if tipo_evento in ("PAYMENT_CONFIRMED", "PAYMENT_RECEIVED") and not pagamento_ja_ativado:
            reiniciar = modo_op != "upgrade"
            atualizar_plano_assinatura(
                db=db,
                advogado_id=assinatura.advogado_id,
                tier=tier_alvo if tier_alvo in CATALOGO_PLANOS else assinatura.tier,
                asaas_subscription_id=subscription_id or assinatura.asaas_subscription_id,
                checkout_url="",
                status="active",
                reiniciar_ciclo=reiniciar,
            )
            assinatura.checkout_url = None
        elif tipo_evento == "PAYMENT_OVERDUE":
            assinatura.status = "past_due"
        elif tipo_evento in ("SUBSCRIPTION_DELETED", "SUBSCRIPTION_INACTIVATED"):
            if assinatura.ciclo_fim and not _ciclo_mensal_expirado(assinatura.ciclo_fim):
                assinatura.status = "canceling"
            else:
                assinatura.status = "canceled"
            assinatura.asaas_subscription_id = None
            assinatura.checkout_url = None

    db.commit()
    return {"status": "processed", "event_id": event_id, "event": tipo_evento}
