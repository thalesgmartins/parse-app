"""Testes unitários para isolamento multi-tenant por schema, quotas mensais e fail-fast CNIS."""

import uuid
from collections.abc import Generator
from pathlib import Path
from unittest.mock import patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.parser import validar_cabecalho_cnis_rapido, validar_texto_cabecalho_cnis
from app.database.models import Base
from app.database.repository import criar_advogado, criar_job_extracao
from app.database.tenancy import (
    ativar_schema_tenant,
    gerar_nome_schema,
    obter_mapa_schema,
    validar_nome_schema,
)
from app.services.quotas import (
    LimiteAbusoDiarioError,
    QuotaInsuficienteError,
    atualizar_plano_assinatura,
    confirmar_consumo_credito,
    estornar_reserva_credito,
    obter_resumo_quota,
    reservar_creditos_extracao,
)
from app.services.worker import processar_job_extracao


@pytest.fixture
def db_session() -> Generator[Session, None, None]:
    """Cria sessão isolada em SQLite em memória para testes de tenancy e quotas."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    factory = sessionmaker(bind=engine)
    session = factory()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)


def test_gerar_e_validar_nome_schema_seguro() -> None:
    """Garante que o nome do schema do tenant seja determinístico e imune a injeção."""
    # Arrange
    adv_id = uuid.UUID("7a9fa9f6-c161-480d-8aaf-16f6673b49ec")

    # Act
    schema = gerar_nome_schema(adv_id)
    validado = validar_nome_schema(schema)
    mapa_pg = obter_mapa_schema(schema, dialeto_sqlite=False)
    mapa_sqlite = obter_mapa_schema(schema, dialeto_sqlite=True)

    # Assert
    assert schema == "tenant_7a9fa9f6c161480d8aaf16f6673b49ec"
    assert validado == schema
    assert mapa_pg == {"tenant": schema}
    assert mapa_sqlite == {"tenant": None}

    with pytest.raises(ValueError, match="inválido"):
        validar_nome_schema("tenant_drop_table; --")


def test_criar_advogado_provisiona_schema_e_assinatura_trial(db_session: Session) -> None:
    """Verifica que todo novo advogado recebe schema exclusivo e assinatura trial de 3 créditos."""
    # Arrange & Act
    advogado = criar_advogado(
        db_session,
        nome="Dr. Multi Tenant",
        email="tenant@escritorio.com",
        senha="senha",
    )
    resumo = obter_resumo_quota(db_session, advogado.id)
    schema_ativo = ativar_schema_tenant(db_session, schema_name=advogado.schema_name)

    # Assert
    assert advogado.schema_name == f"tenant_{advogado.id.hex}"
    assert schema_ativo == advogado.schema_name
    assert db_session.info.get("tenant_schema") == advogado.schema_name
    assert resumo.tier == "trial"
    assert resumo.limite_mensal == 3
    assert resumo.creditos_restantes == 3


def test_reserva_confirmacao_e_bloqueio_de_quota_mensal(db_session: Session) -> None:
    """Valida a reserva atômica, bloqueio por excesso e confirmação de créditos."""
    # Arrange
    advogado = criar_advogado(
        db_session,
        nome="Dra. Quota",
        email="quota@escritorio.com",
        senha="senha",
    )

    # Act: Reserva 2 dos 3 créditos do plano Trial
    reservar_creditos_extracao(db_session, advogado.id, quantidade=2)
    resumo_parcial = obter_resumo_quota(db_session, advogado.id)

    # Assert parcial: 2 reservados, resta 1 disponível
    assert resumo_parcial.creditos_reservados == 2
    assert resumo_parcial.creditos_restantes == 1

    # Act & Assert: Tentar enviar lote de 2 arquivos quando só resta 1 deve bloquear
    with pytest.raises(QuotaInsuficienteError) as exc_info:
        reservar_creditos_extracao(db_session, advogado.id, quantidade=2)
    assert exc_info.value.restantes == 1
    assert exc_info.value.solicitados == 2

    # Confirma consumo de 1 crédito
    confirmar_consumo_credito(db_session, advogado.id)
    resumo_apos_confirmar = obter_resumo_quota(db_session, advogado.id)
    assert resumo_apos_confirmar.creditos_consumidos == 1
    assert resumo_apos_confirmar.creditos_reservados == 1


def test_estorno_de_credito_em_pdf_nao_cnis_e_protecao_anti_abuso(
    db_session: Session,
    tmp_path: Path,
) -> None:
    """Garante que PDFs não-CNIS não descontem da franquia paga, mas ativem bloqueio anti-abuso."""
    # Arrange
    advogado = criar_advogado(
        db_session,
        nome="Dr. Protecao",
        email="protecao@escritorio.com",
        senha="senha",
    )
    atualizar_plano_assinatura(db_session, advogado.id, tier="autonomo")

    # Reserva 1 crédito e processa um PDF inválido (0 competências)
    reservar_creditos_extracao(db_session, advogado.id, quantidade=1)
    pdf_invalido = tmp_path / "procuracao_cliente.pdf"
    pdf_invalido.write_bytes(b"%PDF-1.4 fake non-cnis")

    job_id = uuid.uuid4()
    criar_job_extracao(
        db=db_session,
        job_id=job_id,
        advogado_id=advogado.id,
        nome_arquivo="procuracao_cliente.pdf",
        caminho_arquivo_temp=str(pdf_invalido),
    )

    # Act
    with patch("app.services.worker.extrair_dados_pdf", return_value=[]):
        sucesso = processar_job_extracao(job_id=job_id, db=db_session)

    # Assert: Crédito foi devolvido (0 consumidos, 30 restantes), mas contou 1 erro hoje
    assert sucesso is False
    resumo = obter_resumo_quota(db_session, advogado.id)
    assert resumo.creditos_consumidos == 0
    assert resumo.creditos_reservados == 0
    assert resumo.creditos_restantes == 30
    assert resumo.erros_validacao_hoje == 1

    # Simula atingir o teto diário de rejeições anti-abuso (10 arquivos inválidos)
    for _ in range(9):
        estornar_reserva_credito(db_session, advogado.id, arquivo_invalido=True)

    with pytest.raises(LimiteAbusoDiarioError):
        reservar_creditos_extracao(db_session, advogado.id, quantidade=1)


def test_validar_cabecalho_cnis_rapido_fail_fast(tmp_path: Path) -> None:
    """Verifica a detecção rápida de cabeçalho CNIS na primeira página."""
    # Arrange & Act & Assert
    assert validar_texto_cabecalho_cnis("EXTRATO PREVIDENCIARIO - CNIS - INSS") is True
    assert validar_texto_cabecalho_cnis("01/2024 2.500,00") is True
    assert validar_texto_cabecalho_cnis("CONTRATO DE LOCACAO DE IMOVEL COMERCIAL") is False
    assert validar_cabecalho_cnis_rapido(tmp_path / "nao_existe.pdf") is False
