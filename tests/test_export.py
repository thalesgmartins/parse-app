"""Testes unitários e de integração para exportação de dados e histórico."""

import uuid
from collections.abc import Generator
from datetime import datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.schemas import CnisCompetencia
from app.core.security import create_access_token
from app.database.models import Advogado, Base, Contribuicao
from app.database.repository import (
    concluir_job,
    criar_advogado,
    criar_cliente,
    criar_job_extracao,
    listar_jobs_por_advogado,
    obter_cliente_por_id,
    obter_contribuicoes_por_cliente,
    salvar_contribuicoes,
)
from app.database.session import get_db
from app.main import app
from app.services.export import gerar_csv_contribuicoes


@pytest.fixture
def db_session() -> Generator[Session, None, None]:
    """Cria uma sessão isolada com SQLite em memória."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    session_factory = sessionmaker(bind=engine)
    session = session_factory()

    yield session

    session.close()
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def test_setup() -> Generator[tuple[TestClient, Advogado, Session], None, None]:
    """Fornece um TestClient autenticado e a sessão do banco em memória."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    session_factory = sessionmaker(bind=engine)
    session = session_factory()

    advogado = Advogado(
        nome="Dr. Export",
        email="export@adv.com",
        senha_hash="hashfake123",
    )
    session.add(advogado)
    session.commit()
    session.refresh(advogado)

    def override_get_db() -> Generator[Session, None, None]:
        db_sess = session_factory()
        try:
            yield db_sess
        finally:
            db_sess.close()

    app.dependency_overrides[get_db] = override_get_db

    with TestClient(app) as test_client:
        token = create_access_token({"sub": str(advogado.id), "email": advogado.email})
        test_client.cookies.set("access_token", token)
        yield test_client, advogado, session

    app.dependency_overrides.clear()
    session.close()
    Base.metadata.drop_all(bind=engine)


def test_gerar_csv_contribuicoes_formato_brasileiro() -> None:
    """Verifica formatação do CSV com BOM UTF-8, ponto e vírgula e vírgula decimal."""
    # Arrange
    itens = [
        Contribuicao(data_competencia="10/2024", valor=1750.50),
        Contribuicao(data_competencia="11/2024", valor=2000.00),
    ]

    # Act
    csv_resultado = gerar_csv_contribuicoes(itens)

    # Assert
    assert csv_resultado.startswith("\ufeff")
    linhas = csv_resultado.strip("\ufeff").split("\r\n")
    assert linhas[0] == "Competência;Remuneração (R$)"
    assert linhas[1] == "10/2024;1750,50"
    assert linhas[2] == "11/2024;2000,00"


def test_repositorio_obter_cliente_por_id(db_session: Session) -> None:
    """Valida busca de cliente por ID."""
    # Arrange
    advogado = criar_advogado(db_session, "Dr. Teste", "t@adv.com", "senha")
    cliente = criar_cliente(db_session, advogado.id, "Segurado Teste", "11122233344")

    # Act
    encontrado = obter_cliente_por_id(db_session, cliente.id)
    inexistente = obter_cliente_por_id(db_session, uuid.uuid4())

    # Assert
    assert encontrado is not None
    assert encontrado.id == cliente.id
    assert encontrado.nome == "Segurado Teste"
    assert inexistente is None


def test_repositorio_listar_jobs_por_advogado(db_session: Session) -> None:
    """Valida listagem de jobs ordenados decrescentemente pela data de criação."""
    # Arrange
    advogado = criar_advogado(db_session, "Dr. Teste", "t@adv.com", "senha")
    job1_id = uuid.uuid4()
    job2_id = uuid.uuid4()

    job1 = criar_job_extracao(
        db_session,
        job_id=job1_id,
        advogado_id=advogado.id,
        nome_arquivo="cnis_primeiro.pdf",
    )
    job1.created_at = datetime(2026, 1, 1, 10, 0, 0)
    job2 = criar_job_extracao(
        db_session,
        job_id=job2_id,
        advogado_id=advogado.id,
        nome_arquivo="cnis_segundo.pdf",
    )
    job2.created_at = datetime(2026, 1, 1, 12, 0, 0)
    db_session.commit()

    # Act
    jobs = listar_jobs_por_advogado(db_session, advogado.id)

    # Assert
    assert len(jobs) == 2
    # O mais recente aparece primeiro
    assert jobs[0].id == job2_id
    assert jobs[1].id == job1_id


def test_repositorio_obter_contribuicoes_por_cliente_cronologico(
    db_session: Session,
) -> None:
    """Verifica se contribuições de um cliente são retornadas em ordem cronológica."""
    # Arrange
    advogado = criar_advogado(db_session, "Dr. Teste", "t@adv.com", "senha")
    cliente = criar_cliente(db_session, advogado.id, "Segurado Ordenado")
    competencias = [
        CnisCompetencia(data_competencia="02/2025", valor=1800.0),
        CnisCompetencia(data_competencia="12/2024", valor=1500.0),
        CnisCompetencia(data_competencia="01/2025", valor=1700.0),
    ]
    salvar_contribuicoes(db_session, cliente_id=cliente.id, lista=competencias)

    # Act
    contribuicoes = obter_contribuicoes_por_cliente(db_session, cliente.id)

    # Assert
    datas = [c.data_competencia for c in contribuicoes]
    assert datas == ["12/2024", "01/2025", "02/2025"]


def test_endpoint_exportar_job_csv_sucesso(
    test_setup: tuple[TestClient, Advogado, Session],
) -> None:
    """Valida download de CSV para um job concluído pertencente ao advogado."""
    # Arrange
    client, advogado, session = test_setup
    job_id = uuid.uuid4()
    job = criar_job_extracao(
        session,
        job_id=job_id,
        advogado_id=advogado.id,
        nome_arquivo="extrato_oficial.pdf",
    )
    concluir_job(session, job_id=job.id, total_competencias=2)
    salvar_contribuicoes(
        session,
        cliente_id=None,
        lista=[
            CnisCompetencia(data_competencia="05/2024", valor=2100.0),
            CnisCompetencia(data_competencia="06/2024", valor=2200.0),
        ],
        job_id=job.id,
    )

    # Act
    response = client.get(f"/cnis/jobs/{job.id}/csv")

    # Assert
    assert response.status_code == 200
    assert "text/csv" in response.headers["content-type"]
    assert "attachment; filename=" in response.headers["content-disposition"]
    conteudo = response.text
    assert "05/2024;2100,00" in conteudo
    assert "06/2024;2200,00" in conteudo


def test_endpoint_exportar_job_csv_nao_concluido(
    test_setup: tuple[TestClient, Advogado, Session],
) -> None:
    """Garante que tentativa de exportar job pendente/falho retorna status 400."""
    # Arrange
    client, advogado, session = test_setup
    job_id = uuid.uuid4()
    job = criar_job_extracao(
        session,
        job_id=job_id,
        advogado_id=advogado.id,
        nome_arquivo="extrato_pendente.pdf",
    )

    # Act
    response = client.get(f"/cnis/jobs/{job.id}/csv")

    # Assert
    assert response.status_code == 400
    assert "não foi concluído" in response.json()["detail"]


def test_endpoint_exportar_job_csv_outro_advogado(
    test_setup: tuple[TestClient, Advogado, Session],
) -> None:
    """Garante isolamento multi-tenant impedindo acesso a job de outro advogado."""
    # Arrange
    client, _, session = test_setup
    outro_advogado = criar_advogado(session, "Outro Dr.", "outro@adv.com", "senha")
    job_id = uuid.uuid4()
    job = criar_job_extracao(
        session,
        job_id=job_id,
        advogado_id=outro_advogado.id,
        nome_arquivo="extrato_outro.pdf",
    )
    concluir_job(session, job_id=job.id, total_competencias=1)

    # Act
    response = client.get(f"/cnis/jobs/{job.id}/csv")

    # Assert
    assert response.status_code == 404


def test_endpoint_exportar_cliente_csv_sucesso(
    test_setup: tuple[TestClient, Advogado, Session],
) -> None:
    """Valida download de CSV para histórico completo de um cliente."""
    # Arrange
    client, advogado, session = test_setup
    cliente = criar_cliente(session, advogado.id, "Carlos Drummond")
    salvar_contribuicoes(
        session,
        cliente_id=cliente.id,
        lista=[CnisCompetencia(data_competencia="03/2023", valor=3200.75)],
    )

    # Act
    response = client.get(f"/cnis/clientes/{cliente.id}/csv")

    # Assert
    assert response.status_code == 200
    assert "text/csv" in response.headers["content-type"]
    assert "carlos_drummond.csv" in response.headers["content-disposition"]
    assert "03/2023;3200,75" in response.text


def test_dashboard_renderiza_historico_de_jobs(
    test_setup: tuple[TestClient, Advogado, Session],
) -> None:
    """Verifica se a página do dashboard exibe a tabela de extratos processados."""
    # Arrange
    client, advogado, session = test_setup
    job_id = uuid.uuid4()
    job = criar_job_extracao(
        session,
        job_id=job_id,
        advogado_id=advogado.id,
        nome_arquivo="documento_historico.pdf",
    )
    concluir_job(session, job_id=job.id, total_competencias=5)

    # Act
    response = client.get("/dashboard")

    # Assert
    assert response.status_code == 200
    assert "Extratos Processados Anteriormente" in response.text
    assert "documento_historico.pdf" in response.text
    assert "Concluído" in response.text
