"""Testes de integração para as rotas assíncronas de extração CNIS e HTMX."""

import io
import uuid
from collections.abc import Generator
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.schemas import CnisCompetencia
from app.core.security import create_access_token
from app.database.models import Advogado
from app.database.repository import (
    criar_cliente,
    criar_job_extracao,
    falhar_job,
    salvar_contribuicoes,
)
from app.database.session import SessionLocal
from app.main import app


@pytest.fixture
def auth_client() -> Generator[tuple[TestClient, Advogado, Session], None, None]:
    """Fornece um TestClient com usuário autenticado e banco em memória."""
    session = SessionLocal()

    advogado = Advogado(
        nome="Dr. Assíncrono",
        email=f"async_{uuid.uuid4().hex[:8]}@adv.com",
        senha_hash="hashfake123",
    )
    session.add(advogado)
    session.commit()
    session.refresh(advogado)

    with TestClient(app) as test_client:
        token = create_access_token({"sub": str(advogado.id), "email": advogado.email})
        test_client.cookies.set("access_token", token)
        yield test_client, advogado, session

    session.close()


def test_extrair_html_rejeita_arquivo_nao_pdf(
    auth_client: tuple[TestClient, Advogado, Session],
) -> None:
    """Garante que a submissão de arquivo não-PDF exibe mensagem de erro amigável."""
    client, _, _ = auth_client
    fake_txt = io.BytesIO(b"conteudo de texto puro")

    response = client.post(
        "/cnis/extrair-html",
        data={"cliente_id": "00000000-0000-0000-0000-000000000000"},
        files={"arquivo": ("documento.txt", fake_txt, "text/plain")},
    )

    assert response.status_code == 200
    assert "Falha no Processamento do Documento" in response.text
    assert "Apenas arquivos no formato PDF" in response.text


def test_extrair_html_enfileira_job_e_retorna_poller_htmx(
    auth_client: tuple[TestClient, Advogado, Session],
) -> None:
    """Verifica que o upload válido retorna imediatamente o componente de polling do HTMX."""
    client, advogado, session = auth_client
    cliente = criar_cliente(session, advogado_id=advogado.id, nome="Titular Teste")

    fake_pdf = io.BytesIO(b"%PDF-1.4 fake stream")

    with patch(
        "app.services.worker.extrair_dados_pdf",
        return_value=[CnisCompetencia(data_competencia="03/2021", valor=1800.0)],
    ):
        response = client.post(
            "/cnis/extrair-html",
            data={"cliente_id": str(cliente.id)},
            files={"arquivo": ("extrato_previdenciario.pdf", fake_pdf, "application/pdf")},
        )

    assert response.status_code == 200
    assert "job-status-poller" in response.text
    assert 'hx-trigger="every 1s"' in response.text
    assert "extrato_previdenciario.pdf" in response.text


def test_get_job_polling_em_andamento(
    auth_client: tuple[TestClient, Advogado, Session],
) -> None:
    """Verifica que job com status pending ou processing mantém o poller ativo."""
    client, advogado, session = auth_client
    job_id = uuid.uuid4()

    job = criar_job_extracao(
        db=session,
        job_id=job_id,
        advogado_id=advogado.id,
        nome_arquivo="aguardando.pdf",
    )
    job.status = "processing"
    session.commit()

    response = client.get(f"/cnis/jobs/{job_id}")

    assert response.status_code == 200
    assert 'hx-trigger="every 1s"' in response.text
    assert "Processando Extrato CNIS" in response.text


def test_get_job_concluido_renderiza_tabela_e_interrompe_polling(
    auth_client: tuple[TestClient, Advogado, Session],
) -> None:
    """Verifica que job concluído devolve a tabela de resultados sem trigger de polling."""
    client, advogado, session = auth_client
    cliente = criar_cliente(session, advogado_id=advogado.id, nome="Aposentado Silva")
    job_id = uuid.uuid4()

    job = criar_job_extracao(
        db=session,
        job_id=job_id,
        advogado_id=advogado.id,
        cliente_id=cliente.id,
        nome_arquivo="concluido.pdf",
    )
    job.status = "completed"
    job.total_competencias = 1
    session.commit()

    salvar_contribuicoes(
        db=session,
        cliente_id=cliente.id,
        lista=[CnisCompetencia(data_competencia="07/2021", valor=3450.75)],
        job_id=job_id,
    )

    response = client.get(f"/cnis/jobs/{job_id}")

    assert response.status_code == 200
    # Polling termina pois o fragmento tabela_resultados não possui hx-trigger
    assert 'hx-trigger="every 1s"' not in response.text
    assert "Extrato Processado com Sucesso" in response.text
    assert "07/2021" in response.text
    assert "3450,75" in response.text


def test_get_job_falho_renderiza_card_erro(
    auth_client: tuple[TestClient, Advogado, Session],
) -> None:
    """Verifica que job com falha renderiza o alerta de erro amigável."""
    client, advogado, session = auth_client
    job_id = uuid.uuid4()

    criar_job_extracao(
        db=session,
        job_id=job_id,
        advogado_id=advogado.id,
        nome_arquivo="falha.pdf",
    )
    falhar_job(session, job_id=job_id, mensagem_erro="PDF sem texto pesquisável.")

    response = client.get(f"/cnis/jobs/{job_id}")

    assert response.status_code == 200
    assert 'hx-trigger="every 1s"' not in response.text
    assert "Falha no Processamento do Documento" in response.text
    assert "PDF sem texto pesquisável." in response.text


def test_get_job_status_json_endpoint(
    auth_client: tuple[TestClient, Advogado, Session],
) -> None:
    """Verifica o endpoint REST JSON /cnis/jobs/{job_id}/status."""
    client, advogado, session = auth_client
    job_id = uuid.uuid4()

    criar_job_extracao(
        db=session,
        job_id=job_id,
        advogado_id=advogado.id,
        nome_arquivo="api_check.pdf",
    )

    response = client.get(f"/cnis/jobs/{job_id}/status")

    assert response.status_code == 200
    data = response.json()
    assert data["id"] == str(job_id)
    assert data["status"] == "pending"
    assert data["nome_arquivo"] == "api_check.pdf"


def test_get_job_retorna_404_para_outro_advogado(
    auth_client: tuple[TestClient, Advogado, Session],
) -> None:
    """Garante isolamento multi-inquilino impedindo acesso a jobs de terceiros."""
    client, _, session = auth_client

    outro_advogado = Advogado(
        nome="Outro Advogado",
        email="outro@adv.com",
        senha_hash="hash",
    )
    session.add(outro_advogado)
    session.commit()

    job_id = uuid.uuid4()
    criar_job_extracao(
        db=session,
        job_id=job_id,
        advogado_id=outro_advogado.id,
        nome_arquivo="secreto.pdf",
    )

    response = client.get(f"/cnis/jobs/{job_id}")
    assert response.status_code == 404


def test_post_extrair_json_api(
    auth_client: tuple[TestClient, Advogado, Session],
) -> None:
    """Verifica o endpoint JSON /cnis/extrair retornando job enfileirado."""
    client, _, _ = auth_client
    fake_pdf = io.BytesIO(b"%PDF-1.4 stream json")

    with patch(
        "app.services.worker.extrair_dados_pdf",
        return_value=[],
    ):
        response = client.post(
            "/cnis/extrair",
            files={"arquivo": ("extrato.pdf", fake_pdf, "application/pdf")},
        )

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "pending"
    assert "job_id" in data
    assert data["nome_arquivo"] == "extrato.pdf"
