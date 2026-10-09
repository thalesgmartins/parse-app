"""Testes de integração para as rotas web, assets estáticos e fragmentos HTMX."""

import io
from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.security import create_access_token
from app.database.models import Advogado, Base
from app.database.session import get_db
from app.main import app


@pytest.fixture
def client_with_user() -> Generator[tuple[TestClient, Advogado], None, None]:
    """Fornece um TestClient com usuário autenticado e banco em memória."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    session_factory = sessionmaker(bind=engine)
    session = session_factory()

    advogado = Advogado(
        nome="Dr. Teste Web",
        email="teste.web@adv.com",
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
        yield test_client, advogado

    app.dependency_overrides.clear()
    session.close()
    Base.metadata.drop_all(bind=engine)


def test_assets_estaticos_sao_servidos() -> None:
    """Garante que os arquivos locais de Tailwind, HTMX e imagens da marca são servidos."""
    # Arrange & Act
    with TestClient(app) as client:
        res_css = client.get("/static/css/tailwind.min.css")
        res_js = client.get("/static/js/htmx.min.js")
        res_favicon = client.get("/static/images/favicon.png")
        res_logo = client.get("/static/images/parse-logo-vazada-branca.png")

    # Assert
    assert res_css.status_code == 200
    assert "text/css" in res_css.headers.get("content-type", "")
    assert res_js.status_code == 200
    assert res_favicon.status_code == 200
    assert res_logo.status_code == 200


def test_dashboard_redireciona_se_deslogado() -> None:
    """Verifica que o acesso a /dashboard sem cookie de autenticação redireciona para login."""
    # Arrange & Act
    with TestClient(app) as client:
        response = client.get("/dashboard", follow_redirects=False)

    # Assert
    assert response.status_code == 303
    assert response.headers.get("location") == "/login"


def test_dashboard_renderiza_com_usuario_autenticado(
    client_with_user: tuple[TestClient, Advogado],
) -> None:
    """Verifica se a dashboard carrega com dados do usuário e botão de logout."""
    # Arrange
    client, advogado = client_with_user

    # Act
    response = client.get("/dashboard")

    # Assert
    assert response.status_code == 200
    assert advogado.email in response.text
    assert "/auth/logout" in response.text
    assert "hx-indicator" in response.text
    assert "parse-logo-vazada-branca.png" in response.text


def test_extrair_html_rejeita_arquivo_nao_pdf(
    client_with_user: tuple[TestClient, Advogado],
) -> None:
    """Verifica se /cnis/extrair-html devolve mensagem de erro amigável para não-PDFs."""
    # Arrange
    client, _ = client_with_user
    fake_txt = io.BytesIO(b"conteudo de texto puro")

    # Act
    response = client.post(
        "/cnis/extrair-html",
        data={"cliente_id": "00000000-0000-0000-0000-000000000000"},
        files={"arquivo": ("documento.txt", fake_txt, "text/plain")},
    )

    # Assert
    assert response.status_code == 200
    assert "Falha no Processamento do Documento" in response.text
    assert "Apenas arquivos no formato PDF" in response.text


def test_login_erro_via_navegador_redireciona_para_tela_login(
    client_with_user: tuple[TestClient, Advogado],
) -> None:
    """Garante que requisição do navegador com erro no login redireciona para /login?erro=..."""
    # Arrange
    client, _ = client_with_user

    # Act
    response = client.post(
        "/auth/login",
        data={"email": "inexistente@adv.com", "password": "senha"},
        headers={"Accept": "text/html,application/xhtml+xml"},
        follow_redirects=False,
    )

    # Assert
    assert response.status_code == 303
    assert response.headers.get("location") == "/login?erro=Email+ou+senha+incorretos."


def test_tela_login_renderiza_mensagem_de_erro_quando_passada() -> None:
    """Verifica se a rota /login exibe o banner visual de erro quando presente."""
    # Arrange & Act
    with TestClient(app) as client:
        response = client.get("/login?erro=Credenciais+invalidas")

    # Assert
    assert response.status_code == 200
    assert "Credenciais invalidas" in response.text
    assert "parse-logo-vazada-preta.png" in response.text


def test_rota_raiz_redireciona_para_login_se_deslogado() -> None:
    """Verifica que o acesso à rota raiz / sem sessão redireciona para /login."""
    # Arrange & Act
    with TestClient(app) as client:
        response = client.get("/", follow_redirects=False)

    # Assert
    assert response.status_code == 303
    assert response.headers.get("location") == "/login"


def test_rota_raiz_redireciona_para_dashboard_se_autenticado(
    client_with_user: tuple[TestClient, Advogado],
) -> None:
    """Verifica que o acesso à rota raiz / com sessão redireciona para /dashboard."""
    # Arrange
    client, _ = client_with_user

    # Act
    response = client.get("/", follow_redirects=False)

    # Assert
    assert response.status_code == 303
    assert response.headers.get("location") == "/dashboard"
