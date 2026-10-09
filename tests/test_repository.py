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
    obter_ou_criar_cliente_por_dados,
    registrar_log_extracao,
    salvar_contribuicoes,
    salvar_ou_atualizar_contribuicoes,
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


def test_obter_ou_criar_cliente_por_dados_novo(db_session: Session) -> None:
    """Verifica a criação de um novo cliente quando inexistente no banco."""
    # Arrange
    advogado = criar_advogado(db_session, nome="Dr. Santos", email="santos@teste.com", senha="123")

    # Act
    cliente = obter_ou_criar_cliente_por_dados(
        db_session,
        advogado_id=advogado.id,
        nome="Lucas Oliveira",
        cpf="111.222.333-44",
    )

    # Assert
    assert cliente.id is not None
    assert cliente.nome == "Lucas Oliveira"
    assert cliente.cpf == "111.222.333-44"
    assert cliente.advogado_id == advogado.id


def test_obter_ou_criar_cliente_por_dados_reutiliza_por_cpf(db_session: Session) -> None:
    """Verifica a reutilização do cliente pelo CPF e atualização de nome genérico."""
    # Arrange
    advogado = criar_advogado(db_session, nome="Dr. Souza", email="souza@teste.com", senha="123")
    cliente_inicial = obter_ou_criar_cliente_por_dados(
        db_session,
        advogado_id=advogado.id,
        nome=None,
        cpf="555.666.777-88",
        nome_arquivo="extrato_sem_nome.pdf",
    )
    assert cliente_inicial.nome.startswith("Segurado")

    # Act
    cliente_recuperado = obter_ou_criar_cliente_por_dados(
        db_session,
        advogado_id=advogado.id,
        nome="Carlos Silva",
        cpf="55566677788",  # Sem pontuação
    )

    # Assert
    assert cliente_recuperado.id == cliente_inicial.id
    assert cliente_recuperado.nome == "Carlos Silva"


def test_obter_ou_criar_cliente_por_dados_previne_colisao_homonimos(
    db_session: Session,
) -> None:
    """Garante que homônimos com CPFs distintos não sobrescrevam um ao outro."""
    # Arrange
    advogado = criar_advogado(db_session, nome="Dra. Paula", email="paula@teste.com", senha="123")

    # Act
    cliente1 = obter_ou_criar_cliente_por_dados(
        db_session,
        advogado_id=advogado.id,
        nome="João da Silva",
        cpf="111.111.111-11",
    )
    cliente2 = obter_ou_criar_cliente_por_dados(
        db_session,
        advogado_id=advogado.id,
        nome="João da Silva",
        cpf="222.222.222-22",
    )

    # Assert
    assert cliente1.id != cliente2.id
    assert cliente1.cpf == "111.111.111-11"
    assert cliente2.cpf == "222.222.222-22"


def test_salvar_ou_atualizar_contribuicoes_idempotente(db_session: Session) -> None:
    """Valida upsert garantindo que reimportações atualizem dados sem duplicar."""
    # Arrange
    advogado = criar_advogado(db_session, nome="Dr. Prever", email="prever@teste.com", senha="123")
    cliente = criar_cliente(db_session, advogado_id=advogado.id, nome="Maria Clara")

    lote1 = [
        CnisCompetencia(data_competencia="01/2023", valor=1000.0),
        CnisCompetencia(data_competencia="02/2023", valor=1100.0),
    ]
    salvar_ou_atualizar_contribuicoes(db_session, cliente_id=cliente.id, lista=lote1)

    lote2 = [
        CnisCompetencia(data_competencia="02/2023", valor=1250.0),  # Atualização de valor
        CnisCompetencia(data_competencia="03/2023", valor=1300.0),  # Nova competência
    ]

    # Act
    resultado = salvar_ou_atualizar_contribuicoes(db_session, cliente_id=cliente.id, lista=lote2)

    # Assert
    clientes = listar_clientes(db_session, advogado_id=advogado.id)
    assert len(clientes) == 1
    contribuicoes = clientes[0].contribuicoes
    assert len(contribuicoes) == 3

    mapa = {c.data_competencia: c.valor for c in contribuicoes}
    assert mapa["01/2023"] == 1000.0
    assert mapa["02/2023"] == 1250.0
    assert mapa["03/2023"] == 1300.0
    assert len(resultado) == 2


def test_salvar_ou_atualizar_contribuicoes_com_duplicadas_no_mesmo_lote_e_legado(
    db_session: Session,
) -> None:
    """Garante que competências repetidas atualizem pela última leitura sem duplicar."""
    # Arrange
    advogado = criar_advogado(
        db_session, nome="Dr. Deduplica", email="dedup@teste.com", senha="123"
    )
    cliente = criar_cliente(db_session, advogado_id=advogado.id, nome="Segurado Thales")

    # Simula lote contendo a mesma competência repetida (ex: múltiplos vínculos ou leituras)
    lote_com_repeticoes = [
        CnisCompetencia(data_competencia="10/2024", valor=1775.06),
        CnisCompetencia(data_competencia="11/2024", valor=1753.98),
        CnisCompetencia(data_competencia="10/2024", valor=876.08),  # Última leitura de 10/2024
    ]

    # Act
    salvar_ou_atualizar_contribuicoes(db_session, cliente_id=cliente.id, lista=lote_com_repeticoes)

    # Assert
    clientes = listar_clientes(db_session, advogado_id=advogado.id)
    contribuicoes = clientes[0].contribuicoes

    # Apenas 2 competências únicas (10/2024 e 11/2024), sem duplicar 10/2024
    assert len(contribuicoes) == 2
    mapa = {c.data_competencia: c.valor for c in contribuicoes}
    assert mapa["10/2024"] == 876.08  # Atualizado com base na última leitura
    assert mapa["11/2024"] == 1753.98
