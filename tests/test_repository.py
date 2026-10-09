"""Testes unitários para a camada de repositório com SQLAlchemy."""

import uuid
from collections.abc import Generator

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.schemas import CnisCompetencia
from app.database.models import Base
from app.database.repository import (
    criar_advogado,
    criar_cliente,
    criar_job_extracao,
    listar_clientes,
    obter_advogado_por_email,
    obter_advogado_por_id,
    obter_contribuicoes_por_job,
    registrar_log_extracao,
    salvar_contribuicoes,
)


@pytest.fixture
def db_session() -> Generator[Session, None, None]:
    """Cria uma sessão isolada com banco de dados SQLite em memória para testes."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    session_factory = sessionmaker(bind=engine)
    session = session_factory()

    yield session

    session.close()
    Base.metadata.drop_all(bind=engine)


def test_fluxo_advogado_crud(db_session: Session) -> None:
    """Testa criação e busca de advogado por e-mail e ID."""
    # Arrange
    nome = "Doutor Silva"
    email = "silva@advocacia.com"
    senha = "senhaSegura123"

    # Act
    advogado = criar_advogado(db_session, nome=nome, email=email, senha=senha)
    buscado_por_email = obter_advogado_por_email(db_session, email=email)
    buscado_por_id = obter_advogado_por_id(db_session, advogado_id=advogado.id)

    # Assert
    assert buscado_por_email is not None
    assert buscado_por_email.id == advogado.id
    assert buscado_por_email.nome == nome
    assert buscado_por_id is not None
    assert buscado_por_id.email == email


def test_fluxo_cliente_e_contribuicoes(db_session: Session) -> None:
    """Testa criação de clientes, listagem e persistência de contribuições CNIS."""
    # Arrange
    advogado = criar_advogado(
        db_session,
        nome="Dra. Santos",
        email="santos@adv.com",
        senha="senha",
    )

    # Act - Criação de clientes
    cliente1 = criar_cliente(
        db_session,
        advogado_id=advogado.id,
        nome="José da Silva",
        cpf="12345678900",
    )
    criar_cliente(
        db_session,
        advogado_id=advogado.id,
        nome="Ana Pereira",
        cpf="98765432100",
    )

    clientes = listar_clientes(db_session, advogado_id=advogado.id)

    # Assert - Listagem
    assert len(clientes) == 2
    # Ordenado por nome: "Ana Pereira" vem antes de "José da Silva"
    assert clientes[0].nome == "Ana Pereira"
    assert clientes[1].nome == "José da Silva"

    # Act - Salvar contribuições
    competencias = [
        CnisCompetencia(data_competencia="01/2020", valor=1500.50),
        CnisCompetencia(data_competencia="02/2020", valor=1600.75),
    ]
    contribuicoes = salvar_contribuicoes(
        db_session,
        cliente_id=cliente1.id,
        lista=competencias,
    )

    # Assert - Contribuições
    assert len(contribuicoes) == 2
    assert contribuicoes[0].data_competencia == "01/2020"
    assert contribuicoes[0].valor == 1500.50


def test_registro_log_extracao(db_session: Session) -> None:
    """Testa o registro de auditoria na tabela extractions_logs."""
    # Arrange
    advogado = criar_advogado(
        db_session,
        nome="Dr. Oliveira",
        email="oliveira@adv.com",
        senha="senha",
    )

    # Act
    log = registrar_log_extracao(
        db_session,
        advogado_id=advogado.id,
        nome_arquivo="cnis_jose.pdf",
        status="sucesso",
    )

    # Assert
    assert log.id is not None
    assert log.nome_arquivo == "cnis_jose.pdf"
    assert log.status == "sucesso"
    assert log.mensagem_erro is None


def test_obter_contribuicoes_por_job_ordenacao_cronologica(
    db_session: Session,
) -> None:
    """Verifica se contribuições persistidas fora de ordem são retornadas cronologicamente."""
    # Arrange
    advogado = criar_advogado(
        db_session,
        nome="Dr. Previdenciário",
        email="prev@adv.com",
        senha="senha",
    )
    job_id = uuid.uuid4()
    criar_job_extracao(
        db_session,
        job_id=job_id,
        advogado_id=advogado.id,
        nome_arquivo="cnis_desordenado.pdf",
    )
    competencias = [
        CnisCompetencia(data_competencia="12/2025", valor=2000.0),
        CnisCompetencia(data_competencia="12/2024", valor=1800.0),
        CnisCompetencia(data_competencia="11/2025", valor=1950.0),
        CnisCompetencia(data_competencia="11/2024", valor=1750.0),
        CnisCompetencia(data_competencia="10/2024", valor=1700.0),
        CnisCompetencia(data_competencia="01/2025", valor=1850.0),
    ]
    salvar_contribuicoes(
        db_session,
        cliente_id=None,
        lista=competencias,
        job_id=job_id,
    )

    # Act
    contribuicoes = obter_contribuicoes_por_job(db_session, job_id=job_id)

    # Assert
    datas = [c.data_competencia for c in contribuicoes]
    assert datas == [
        "10/2024",
        "11/2024",
        "12/2024",
        "01/2025",
        "11/2025",
        "12/2025",
    ]
