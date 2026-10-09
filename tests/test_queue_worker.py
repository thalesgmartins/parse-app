"""Testes unitários para a fila de jobs e worker assíncrono."""

import uuid
from collections.abc import Generator
from pathlib import Path
from unittest.mock import patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.schemas import CnisCompetencia
from app.database.models import Base
from app.database.repository import (
    bloquear_job_para_processamento,
    concluir_job,
    criar_advogado,
    criar_cliente,
    criar_job_extracao,
    falhar_job,
    obter_cliente_por_id,
    obter_contribuicoes_por_job,
    obter_job_por_id,
    obter_proximo_job,
)
from app.services.worker import (
    processar_job_extracao,
    processar_proximo_job_pendente,
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


def test_criar_e_obter_job_extracao(db_session: Session) -> None:
    """Verifica a criação de um job na fila e sua recuperação por ID."""
    advogado = criar_advogado(db_session, nome="Dr. Fila", email="fila@adv.com", senha="senha")
    job_id = uuid.uuid4()

    job = criar_job_extracao(
        db=db_session,
        job_id=job_id,
        advogado_id=advogado.id,
        nome_arquivo="cnis_teste.pdf",
        caminho_arquivo_temp="/tmp/teste.pdf",
    )

    assert job.id == job_id
    assert job.status == "pending"
    assert job.nome_arquivo == "cnis_teste.pdf"
    assert job.caminho_arquivo_temp == "/tmp/teste.pdf"

    buscado = obter_job_por_id(db_session, job_id)
    assert buscado is not None
    assert buscado.id == job_id
    assert buscado.status == "pending"


def test_obter_proximo_job_e_bloqueio(db_session: Session) -> None:
    """Valida o consumo ordenado e a transição de estado para processing."""
    advogado = criar_advogado(db_session, nome="Dr. Lock", email="lock@adv.com", senha="senha")
    job1_id = uuid.uuid4()
    job2_id = uuid.uuid4()

    criar_job_extracao(
        db=db_session,
        job_id=job1_id,
        advogado_id=advogado.id,
        nome_arquivo="doc1.pdf",
    )
    criar_job_extracao(
        db=db_session,
        job_id=job2_id,
        advogado_id=advogado.id,
        nome_arquivo="doc2.pdf",
    )

    proximo = obter_proximo_job(db_session)
    assert proximo is not None
    assert proximo.id == job1_id

    # Bloqueia o primeiro job
    bloqueado = bloquear_job_para_processamento(db_session, job1_id)
    assert bloqueado is not None
    assert bloqueado.status == "processing"

    # Tentativa de bloquear novamente o mesmo job deve falhar
    assert bloquear_job_para_processamento(db_session, job1_id) is None

    # O próximo pendente agora deve ser o job 2
    segundo = obter_proximo_job(db_session)
    assert segundo is not None
    assert segundo.id == job2_id


def test_concluir_e_falhar_job(db_session: Session) -> None:
    """Verifica as finalizações com sucesso e falha."""
    advogado = criar_advogado(db_session, nome="Dr. Status", email="status@adv.com", senha="senha")
    job_sucesso_id = uuid.uuid4()
    job_erro_id = uuid.uuid4()

    criar_job_extracao(
        db=db_session,
        job_id=job_sucesso_id,
        advogado_id=advogado.id,
        nome_arquivo="ok.pdf",
        caminho_arquivo_temp="/tmp/ok.pdf",
    )
    criar_job_extracao(
        db=db_session,
        job_id=job_erro_id,
        advogado_id=advogado.id,
        nome_arquivo="erro.pdf",
        caminho_arquivo_temp="/tmp/erro.pdf",
    )

    concluido = concluir_job(db_session, job_sucesso_id, total_competencias=42)
    assert concluido is not None
    assert concluido.status == "completed"
    assert concluido.total_competencias == 42
    assert concluido.caminho_arquivo_temp is None

    falho = falhar_job(db_session, job_erro_id, mensagem_erro="PDF corrompido")
    assert falho is not None
    assert falho.status == "failed"
    assert falho.mensagem_erro == "PDF corrompido"
    assert falho.caminho_arquivo_temp is None


def test_processar_job_extracao_sucesso_e_limpeza_arquivo(
    db_session: Session, tmp_path: Path
) -> None:
    """Testa execução bem sucedida do worker e remoção segura do arquivo temporário."""
    advogado = criar_advogado(db_session, nome="Dr. Worker", email="worker@adv.com", senha="senha")
    cliente = criar_cliente(db_session, advogado_id=advogado.id, nome="Segurado Silva")

    # Cria arquivo temporário real
    arquivo_temp = tmp_path / "extrato_efemero.pdf"
    arquivo_temp.write_bytes(b"%PDF-1.4 fake content")
    assert arquivo_temp.exists()

    job_id = uuid.uuid4()
    criar_job_extracao(
        db=db_session,
        job_id=job_id,
        advogado_id=advogado.id,
        cliente_id=cliente.id,
        nome_arquivo="extrato_efemero.pdf",
        caminho_arquivo_temp=str(arquivo_temp),
    )

    competencias_fakes = [
        CnisCompetencia(data_competencia="05/2021", valor=2200.0),
        CnisCompetencia(data_competencia="06/2021", valor=2300.0),
    ]

    with patch("app.services.worker.extrair_dados_pdf", return_value=competencias_fakes):
        sucesso = processar_job_extracao(job_id=job_id, db=db_session)

    assert sucesso is True

    # Job foi atualizado para completed
    job = obter_job_por_id(db_session, job_id)
    assert job is not None
    assert job.status == "completed"
    assert job.total_competencias == 2

    # Contribuições persistidas
    contribuicoes = obter_contribuicoes_por_job(db_session, job_id)
    assert len(contribuicoes) == 2
    assert contribuicoes[0].data_competencia == "05/2021"
    assert contribuicoes[1].data_competencia == "06/2021"

    # Arquivo temporário deve ter sido removido pelo bloco finally
    assert not arquivo_temp.exists()


def test_processar_job_extracao_arquivo_inexistente(
    db_session: Session,
) -> None:
    """Verifica que o worker transiciona para 'failed' se o arquivo temporário sumir."""
    advogado = criar_advogado(
        db_session, nome="Dr. Missing", email="missing@adv.com", senha="senha"
    )
    job_id = uuid.uuid4()
    criar_job_extracao(
        db=db_session,
        job_id=job_id,
        advogado_id=advogado.id,
        nome_arquivo="inexistente.pdf",
        caminho_arquivo_temp="/tmp/nao_existe_mesmo_9999.pdf",
    )

    sucesso = processar_job_extracao(job_id=job_id, db=db_session)
    assert sucesso is False

    job = obter_job_por_id(db_session, job_id)
    assert job is not None
    assert job.status == "failed"
    assert "não encontrado no disco" in (job.mensagem_erro or "")


def test_processar_proximo_job_pendente_fila(db_session: Session, tmp_path: Path) -> None:
    """Testa fila global consumindo próximo job e retornando False quando esvaziada."""
    advogado = criar_advogado(db_session, nome="Dr. Queue", email="queue@adv.com", senha="senha")

    arquivo_temp = tmp_path / "fila.pdf"
    arquivo_temp.write_bytes(b"%PDF-1.4 fake")

    job_id = uuid.uuid4()
    criar_job_extracao(
        db=db_session,
        job_id=job_id,
        advogado_id=advogado.id,
        nome_arquivo="fila.pdf",
        caminho_arquivo_temp=str(arquivo_temp),
    )

    with patch(
        "app.services.worker.extrair_dados_pdf",
        return_value=[CnisCompetencia(data_competencia="01/2022", valor=1300.0)],
    ):
        consumido = processar_proximo_job_pendente(db=db_session)
        assert consumido is True

    # Segunda chamada não encontra nenhum job pendente
    consumido_novamente = processar_proximo_job_pendente(db=db_session)
    assert consumido_novamente is False


def test_processar_job_extracao_identificacao_automatica_cliente(
    db_session: Session, tmp_path: Path
) -> None:
    """Verifica que o worker detecta o segurado e cria/vincula o cliente automaticamente."""
    # Arrange
    advogado = criar_advogado(
        db_session, nome="Dr. Previdência", email="prev@adv.com", senha="senha"
    )
    arquivo_temp = tmp_path / "extrato_sem_cliente_predefinido.pdf"
    arquivo_temp.write_bytes(b"%PDF-1.4 fake")

    job_id = uuid.uuid4()
    criar_job_extracao(
        db=db_session,
        job_id=job_id,
        advogado_id=advogado.id,
        cliente_id=None,  # Nenhum cliente informado previamente
        nome_arquivo="extrato_sem_cliente_predefinido.pdf",
        caminho_arquivo_temp=str(arquivo_temp),
    )

    competencias = [
        CnisCompetencia(data_competencia="01/2024", valor=1412.0),
        CnisCompetencia(data_competencia="02/2024", valor=1412.0),
    ]

    # Act
    with (
        patch(
            "app.services.worker.extrair_metadados_pdf",
            return_value=("Segurado Identificado Automaticamente", "999.888.777-66"),
        ),
        patch("app.services.worker.extrair_dados_pdf", return_value=competencias),
    ):
        sucesso = processar_job_extracao(job_id=job_id, db=db_session)

    # Assert
    assert sucesso is True
    job_atualizado = obter_job_por_id(db_session, job_id)
    assert job_atualizado is not None
    assert job_atualizado.status == "completed"
    assert job_atualizado.cliente_id is not None

    cliente_criado = obter_cliente_por_id(db_session, job_atualizado.cliente_id)
    assert cliente_criado is not None
    assert cliente_criado.nome == "Segurado Identificado Automaticamente"
    assert cliente_criado.cpf == "999.888.777-66"
    assert len(cliente_criado.contribuicoes) == 2
