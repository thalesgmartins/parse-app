"""Gerenciamento transacional de Planos (Tiers), Quotas Mensais e Proteção Anti-Abuso."""

import uuid
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import MAX_ERROS_VALIDACAO_DIARIO
from app.database.models import Assinatura


@dataclass(frozen=True)
class PlanoTier:
    """Especificação comercial e técnica de um plano de assinatura."""

    codigo: str
    nome: str
    descricao: str
    limite_mensal: int
    valor_mensal: float
    icone_mdi: str
    destaque: bool = False


CATALOGO_PLANOS: dict[str, PlanoTier] = {
    "trial": PlanoTier(
        codigo="trial",
        nome="Degustação Inicial",
        descricao="Acesso inicial para validação da extração automática de extratos CNIS.",
        limite_mensal=3,
        valor_mensal=0.0,
        icone_mdi="mdi-flask-outline",
        destaque=False,
    ),
    "autonomo": PlanoTier(
        codigo="autonomo",
        nome="Advogado Autônomo",
        descricao="Ideal para advogados previdenciários individuais com demanda recorrente.",
        limite_mensal=30,
        valor_mensal=49.90,
        icone_mdi="mdi-account-tie-outline",
        destaque=False,
    ),
    "pequeno_escritorio": PlanoTier(
        codigo="pequeno_escritorio",
        nome="Pequeno Escritório",
        descricao="Para sociedades de advogados com fluxo diário de planejamento e concessão.",
        limite_mensal=150,
        valor_mensal=129.90,
        icone_mdi="mdi-office-building-outline",
        destaque=True,
    ),
    "grande_escritorio": PlanoTier(
        codigo="grande_escritorio",
        nome="Grande Escritório",
        descricao="Alta volumetria para bancas previdenciárias e processamento em lote.",
        limite_mensal=600,
        valor_mensal=299.90,
        icone_mdi="mdi-domain",
        destaque=False,
    ),
}


@dataclass(frozen=True)
class ResumoQuotaAdvogado:
    """Estado consolidado da licença e consumo mensal do advogado para a UI."""

    tier: str
    nome_plano: str
    status: str
    limite_mensal: int
    creditos_consumidos: int
    creditos_reservados: int
    creditos_restantes: int
    percentual_uso: int
    erros_validacao_hoje: int
    max_erros_diario: int
    valor_mensal: float
    checkout_url: str | None


class QuotaInsuficienteError(ValueError):
    """Exceção disparada quando o lote enviado ultrapassa a franquia mensal disponível."""

    def __init__(self, restantes: int, solicitados: int, nome_plano: str) -> None:
        """Inicializa o erro com o saldo atual e a quantidade solicitada."""
        self.restantes = restantes
        self.solicitados = solicitados
        self.nome_plano = nome_plano
        super().__init__(
            f"Limite do plano ({nome_plano}) atingido: você possui {restantes} "
            f"extrato(s) disponível(is) neste ciclo, mas enviou {solicitados} arquivo(s). "
            f"Faça upgrade do seu plano para continuar processando."
        )


class LimiteAbusoDiarioError(ValueError):
    """Exceção disparada quando o usuário excede o limite diário de arquivos não-CNIS."""

    def __init__(self, limite_diario: int) -> None:
        """Inicializa o erro informando o teto diário de segurança."""
        self.limite_diario = limite_diario
        super().__init__(
            f"Proteção anti-abuso ativada: foram identificados {limite_diario} envios "
            f"seguidos de arquivos que não são extratos CNIS hoje. Novos uploads estão "
            f"temporariamente bloqueados até o próximo dia."
        )


def listar_planos_comerciais() -> list[PlanoTier]:
    """Retorna os 3 tiers comerciais disponíveis para assinatura.

    Returns:
        Lista ordenada com Advogado Autônomo, Pequeno Escritório e Grande Escritório.
    """
    return [
        CATALOGO_PLANOS["autonomo"],
        CATALOGO_PLANOS["pequeno_escritorio"],
        CATALOGO_PLANOS["grande_escritorio"],
    ]


def garantir_assinatura_advogado(
    db: Session,
    advogado_id: uuid.UUID | str,
    *,
    com_lock: bool = False,
) -> Assinatura:
    """Recupera ou cria a assinatura padrão (Trial) de um advogado.

    Args:
        db: Sessão ativa do SQLAlchemy.
        advogado_id: Identificador único do advogado.
        com_lock: Se True, aplica SELECT FOR UPDATE em bancos PostgreSQL.

    Returns:
        Instância de Assinatura vinculada ao advogado.
    """
    id_uuid = advogado_id if isinstance(advogado_id, uuid.UUID) else uuid.UUID(str(advogado_id))
    stmt = select(Assinatura).where(Assinatura.advogado_id == id_uuid)
    if com_lock and db.bind is not None and db.bind.dialect.name != "sqlite":
        stmt = stmt.with_for_update()

    assinatura = db.scalar(stmt)
    if assinatura:
        return assinatura

    plano_inicial = CATALOGO_PLANOS["trial"]
    assinatura = Assinatura(
        advogado_id=id_uuid,
        tier=plano_inicial.codigo,
        status="active",
        limite_mensal=plano_inicial.limite_mensal,
        creditos_consumidos=0,
        creditos_reservados=0,
        erros_validacao_hoje=0,
    )
    db.add(assinatura)
    db.commit()
    db.refresh(assinatura)
    return assinatura


def obter_resumo_quota(db: Session, advogado_id: uuid.UUID | str) -> ResumoQuotaAdvogado:
    """Calcula os indicadores de quota mensal e licença para exibição no frontend.

    Args:
        db: Sessão ativa do SQLAlchemy.
        advogado_id: Identificador único do advogado.

    Returns:
        Objeto ResumoQuotaAdvogado pronto para renderização nos templates.
    """
    assinatura = garantir_assinatura_advogado(db, advogado_id)
    plano = CATALOGO_PLANOS.get(assinatura.tier, CATALOGO_PLANOS["trial"])
    hoje_str = date.today().isoformat()
    erros_hoje = assinatura.erros_validacao_hoje if assinatura.data_ultimo_erro == hoje_str else 0
    usados_ou_reservados = assinatura.creditos_consumidos + assinatura.creditos_reservados
    restantes = max(0, assinatura.limite_mensal - usados_ou_reservados)
    pct = (
        min(100, round((usados_ou_reservados / assinatura.limite_mensal) * 100))
        if assinatura.limite_mensal > 0
        else 100
    )
    return ResumoQuotaAdvogado(
        tier=assinatura.tier,
        nome_plano=plano.nome,
        status=assinatura.status,
        limite_mensal=assinatura.limite_mensal,
        creditos_consumidos=assinatura.creditos_consumidos,
        creditos_reservados=assinatura.creditos_reservados,
        creditos_restantes=restantes,
        percentual_uso=pct,
        erros_validacao_hoje=erros_hoje,
        max_erros_diario=MAX_ERROS_VALIDACAO_DIARIO,
        valor_mensal=plano.valor_mensal,
        checkout_url=assinatura.checkout_url,
    )


def reservar_creditos_extracao(
    db: Session,
    advogado_id: uuid.UUID | str,
    quantidade: int = 1,
) -> Assinatura:
    """Reserva créditos atomicamente antes de enfileirar PDFs para extração.

    Previne race conditions quando múltiplos uploads concorrentes ou em lote
    são disparados simultaneamente.

    Args:
        db: Sessão ativa do SQLAlchemy.
        advogado_id: Identificador único do advogado.
        quantidade: Número de arquivos PDF a serem reservados.

    Returns:
        Instância de Assinatura atualizada com os créditos reservados.

    Raises:
        LimiteAbusoDiarioError: Se o usuário atingiu o limite diário de PDFs inválidos.
        QuotaInsuficienteError: Se não houver saldo suficiente na franquia mensal.
    """
    if quantidade <= 0:
        return garantir_assinatura_advogado(db, advogado_id)

    assinatura = garantir_assinatura_advogado(db, advogado_id, com_lock=True)
    plano = CATALOGO_PLANOS.get(assinatura.tier, CATALOGO_PLANOS["trial"])
    hoje_str = date.today().isoformat()

    if assinatura.data_ultimo_erro != hoje_str:
        assinatura.erros_validacao_hoje = 0
        assinatura.data_ultimo_erro = hoje_str

    if assinatura.erros_validacao_hoje >= MAX_ERROS_VALIDACAO_DIARIO:
        db.commit()
        raise LimiteAbusoDiarioError(MAX_ERROS_VALIDACAO_DIARIO)

    ocupados = assinatura.creditos_consumidos + assinatura.creditos_reservados
    restantes = max(0, assinatura.limite_mensal - ocupados)
    if assinatura.status != "active" or quantidade > restantes:
        db.commit()
        raise QuotaInsuficienteError(
            restantes=restantes if assinatura.status == "active" else 0,
            solicitados=quantidade,
            nome_plano=plano.nome,
        )

    assinatura.creditos_reservados += quantidade
    db.commit()
    db.refresh(assinatura)
    return assinatura


def confirmar_consumo_credito(
    db: Session,
    advogado_id: uuid.UUID | str,
) -> Assinatura:
    """Converte 1 crédito reservado em 1 crédito efetivamente consumido após sucesso.

    Args:
        db: Sessão ativa do SQLAlchemy.
        advogado_id: Identificador único do advogado.

    Returns:
        Instância de Assinatura atualizada.
    """
    assinatura = garantir_assinatura_advogado(db, advogado_id, com_lock=True)
    if assinatura.creditos_reservados > 0:
        assinatura.creditos_reservados -= 1
    assinatura.creditos_consumidos += 1
    db.commit()
    db.refresh(assinatura)
    return assinatura


def estornar_reserva_credito(
    db: Session,
    advogado_id: uuid.UUID | str,
    *,
    arquivo_invalido: bool = False,
) -> Assinatura:
    """Devolve 1 crédito reservado caso o arquivo falhe ou não seja um CNIS.

    Não desconta da franquia comercial paga do advogado, mas contabiliza no
    contador diário anti-abuso caso o documento seja inválido.

    Args:
        db: Sessão ativa do SQLAlchemy.
        advogado_id: Identificador único do advogado.
        arquivo_invalido: Se True, incrementa o contador diário de rejeições.

    Returns:
        Instância de Assinatura atualizada.
    """
    assinatura = garantir_assinatura_advogado(db, advogado_id, com_lock=True)
    if assinatura.creditos_reservados > 0:
        assinatura.creditos_reservados -= 1

    if arquivo_invalido:
        hoje_str = date.today().isoformat()
        if assinatura.data_ultimo_erro != hoje_str:
            assinatura.erros_validacao_hoje = 1
            assinatura.data_ultimo_erro = hoje_str
        else:
            assinatura.erros_validacao_hoje += 1

    db.commit()
    db.refresh(assinatura)
    return assinatura


def atualizar_plano_assinatura(
    db: Session,
    advogado_id: uuid.UUID | str,
    tier: str,
    *,
    asaas_customer_id: str | None = None,
    asaas_subscription_id: str | None = None,
    checkout_url: str | None = None,
    status: str = "active",
    reiniciar_ciclo: bool = True,
) -> Assinatura:
    """Atualiza o tier da assinatura do advogado e ajusta o limite mensal.

    Args:
        db: Sessão ativa do SQLAlchemy.
        advogado_id: Identificador único do advogado.
        tier: Código do plano ('autonomo', 'pequeno_escritorio', 'grande_escritorio').
        asaas_customer_id: ID do cliente no Asaas (opcional).
        asaas_subscription_id: ID da assinatura no Asaas (opcional).
        checkout_url: Link da fatura/checkout no Asaas (opcional).
        status: Novo status ('active', 'pending_payment', 'past_due', 'canceled').
        reiniciar_ciclo: Se True, zera os créditos consumidos para o novo ciclo.

    Returns:
        Instância de Assinatura atualizada.

    Raises:
        ValueError: Se o tier informado não existir no catálogo.
    """
    if tier not in CATALOGO_PLANOS:
        raise ValueError(f"Tier de assinatura inválido: {tier}")

    plano = CATALOGO_PLANOS[tier]
    assinatura = garantir_assinatura_advogado(db, advogado_id, com_lock=True)
    assinatura.tier = plano.codigo
    assinatura.limite_mensal = plano.limite_mensal
    assinatura.status = status

    if asaas_customer_id:
        assinatura.asaas_customer_id = asaas_customer_id
    if asaas_subscription_id:
        assinatura.asaas_subscription_id = asaas_subscription_id
    if checkout_url is not None:
        assinatura.checkout_url = checkout_url

    if reiniciar_ciclo and status == "active":
        assinatura.creditos_consumidos = 0
        assinatura.erros_validacao_hoje = 0
        assinatura.ciclo_fim = datetime.now(timezone.utc) + timedelta(days=30)

    db.commit()
    db.refresh(assinatura)
    return assinatura
