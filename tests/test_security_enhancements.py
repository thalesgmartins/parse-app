"""Testes para melhorias de segurança: rate limiting, extração de IP e limite de upload."""

import io
from collections.abc import Generator
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from fastapi import UploadFile
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.cnis import _salvar_arquivo_temporario_com_limite
from app.core.limiter import obter_ip_cliente
from app.core.security import create_access_token
from app.database.models import Advogado, Base
from app.database.session import get_db
from app.main import app


@pytest.fixture
def auth_client() -> Generator[tuple[TestClient, Advogado], None, None]:
    """Fornece um TestClient com usuário autenticado e banco isolado em memória."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    session_factory = sessionmaker(bind=engine)
    session = session_factory()

    advogado = Advogado(
        nome="Dr. Seguranca",
        email="seguranca@adv.com",
        senha_hash="fakehash",
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
        yield test_client, advogado

    app.dependency_overrides.clear()
    session.close()
    Base.metadata.drop_all(bind=engine)


def test_obter_ip_cliente_prioriza_cloudflare() -> None:
    """Verifica se obter_ip_cliente extrai corretamente o cabeçalho CF-Connecting-IP."""
    # Arrange
    request = MagicMock()
    request.headers = {
        "CF-Connecting-IP": "203.0.113.195",
        "X-Forwarded-For": "198.51.100.1",
    }

    # Act
    ip = obter_ip_cliente(request)

    # Assert
    assert ip == "203.0.113.195"


def test_obter_ip_cliente_usa_x_forwarded_for() -> None:
    """Verifica se obter_ip_cliente extrai o primeiro IP de X-Forwarded-For sem Cloudflare."""
    # Arrange
    request = MagicMock()
    request.headers = {"X-Forwarded-For": "198.51.100.42, 10.0.0.1"}

    # Act
    ip = obter_ip_cliente(request)

    # Assert
    assert ip == "198.51.100.42"


def test_obter_ip_cliente_fallback_client_host() -> None:
    """Verifica fallback para request.client.host quando nenhum header de proxy existe."""
    # Arrange
    request = MagicMock()
    request.headers = {}
    request.client.host = "192.168.1.10"

    # Act
    ip = obter_ip_cliente(request)

    # Assert
    assert ip == "192.168.1.10"


def test_salvar_arquivo_temporario_respeita_limite_e_remove_se_excedido(
    tmp_path: Path,
) -> None:
    """Garante que _salvar_arquivo_temporario_com_limite apaga o arquivo se passar do limite."""
    # Arrange
    destino = tmp_path / "arquivo_teste.pdf"
    dados_grandes = b"x" * 1024  # 1 KB
    fake_file = UploadFile(
        file=io.BytesIO(dados_grandes),
        filename="teste.pdf",
    )
    limite = 500  # 500 bytes

    # Act & Assert
    with pytest.raises(ValueError, match="excede o limite máximo"):
        _salvar_arquivo_temporario_com_limite(fake_file, destino, limite_bytes=limite)

    assert not destino.exists()


def test_extrair_api_rejeita_arquivo_acima_do_limite(
    auth_client: tuple[TestClient, Advogado],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verifica que /cnis/extrair retorna HTTP 413 ao receber arquivo maior que o configurado."""
    # Arrange
    client, _ = auth_client
    monkeypatch.setattr("app.api.cnis.MAX_UPLOAD_SIZE_BYTES", 500)
    conteudo_pesado = io.BytesIO(b"%PDF-1.4 " + (b"0" * 1000))

    # Act
    response = client.post(
        "/cnis/extrair",
        files={"arquivo": ("extrato.pdf", conteudo_pesado, "application/pdf")},
    )

    # Assert
    assert response.status_code == 413
    assert "excede o limite máximo" in response.json()["detail"]


def test_extrair_html_rejeita_arquivo_acima_do_limite(
    auth_client: tuple[TestClient, Advogado],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verifica que /cnis/extrair-html renderiza aviso visual de limite excedido."""
    # Arrange
    client, _ = auth_client
    monkeypatch.setattr("app.api.cnis.MAX_UPLOAD_SIZE_BYTES", 500)
    conteudo_pesado = io.BytesIO(b"%PDF-1.4 " + (b"0" * 1000))

    # Act
    response = client.post(
        "/cnis/extrair-html",
        files={"arquivo": ("extrato.pdf", conteudo_pesado, "application/pdf")},
    )

    # Assert
    assert response.status_code == 200
    assert "excede o limite máximo" in response.text


def test_login_rate_limiting_bloqueia_apos_limite() -> None:
    """Verifica que o endpoint /auth/login bloqueia requisições após estourar a cota por IP."""
    # Arrange
    ip_teste = "198.51.100.99"
    headers_api = {
        "CF-Connecting-IP": ip_teste,
        "Accept": "application/json",
    }
    headers_html = {
        "CF-Connecting-IP": ip_teste,
        "Accept": "text/html,application/xhtml+xml",
    }

    with TestClient(app) as client:
        # Act: faz 5 requisições normais (que falham por credencial errada, mas passam pelo limiter)
        for _ in range(5):
            client.post(
                "/auth/login",
                data={"email": "hacker@teste.com", "password": "wrong"},
                headers=headers_api,
            )

        # 6ª tentativa via API (deve ser 429)
        res_bloqueio_api = client.post(
            "/auth/login",
            data={"email": "hacker@teste.com", "password": "wrong"},
            headers=headers_api,
        )

        # 7ª tentativa via Navegador (deve redirecionar com status 303 e parâmetro de erro)
        res_bloqueio_html = client.post(
            "/auth/login",
            data={"email": "hacker@teste.com", "password": "wrong"},
            headers=headers_html,
            follow_redirects=False,
        )

    # Assert
    assert res_bloqueio_api.status_code == 429
    assert res_bloqueio_html.status_code == 303
    assert "erro=Muitas+tentativas+de+acesso" in res_bloqueio_html.headers.get("location", "")
