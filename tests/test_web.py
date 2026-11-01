"""Testes de integração para as rotas web, estatísticas e fragmentos HTMX."""

import io
from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.schemas import CnisCompetencia
from app.core.security import create_access_token
from app.database.models import Advogado, Base, Contribuicao
from app.database.repository import criar_cliente, salvar_contribuicoes
from app.database.session import get_db
from app.main import app
from app.services.analytics import construir_painel_analise, formatar_moeda_br


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
        token = create_access_token(
            {"sub": str(advogado.id), "email": advogado.email}
        )
        test_client.cookies.set("access_token", token)
        yield test_client, advogado

    app.dependency_overrides.clear()
    session.close()
    Base.metadata.drop_all(bind=engine)


def test_assets_estaticos_sao_servidos() -> None:
    """Garante que os arquivos locais de Tailwind, HTMX e imagens são servidos."""
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
    """Verifica que o acesso a /dashboard sem cookie redireciona para /login."""
    # Arrange & Act
    with TestClient(app) as client:
        response = client.get("/dashboard", follow_redirects=False)

    # Assert
    assert response.status_code == 303
    assert response.headers.get("location") == "/login"


def test_dashboard_renderiza_com_usuario_autenticado(
    client_with_user: tuple[TestClient, Advogado],
) -> None:
    """Verifica se a dashboard carrega em modo escuro com sidebar e upload."""
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
    assert "#121212" in response.text
    assert "#2a389b" in response.text


def test_tela_analise_redireciona_se_deslogado() -> None:
    """Verifica que o acesso a /analise sem sessão redireciona para /login."""
    # Arrange & Act
    with TestClient(app) as client:
        response = client.get("/analise", follow_redirects=False)

    # Assert
    assert response.status_code == 303
    assert response.headers.get("location") == "/login"


def test_tela_analise_renderiza_kpis_grafico_e_tabela(
    client_with_user: tuple[TestClient, Advogado],
) -> None:
    """Verifica se /analise renderiza KPIs, curva salarial SVG e competências."""
    # Arrange
    client, advogado = client_with_user
    override_fn = app.dependency_overrides[get_db]
    db_gen = override_fn()
    db_sess = next(db_gen)
    try:
        segurado = criar_cliente(
            db_sess,
            advogado_id=advogado.id,
            nome="Segurado Analítico",
            cpf="123.456.789-00",
        )
        salvar_contribuicoes(
            db_sess,
            cliente_id=segurado.id,
            lista=[
                CnisCompetencia(data_competencia="01/2023", valor=3200.00),
                CnisCompetencia(data_competencia="02/2023", valor=4800.50),
                CnisCompetencia(data_competencia="03/2023", valor=7500.00),
            ],
        )
        segurado_id = str(segurado.id)
    finally:
        db_sess.close()

    # Act
    response = client.get(f"/analise?cliente_id={segurado_id}")

    # Assert
    assert response.status_code == 200
    assert "Segurado Analítico" in response.text
    assert "Remuneração Média" in response.text
    assert "Teto Previdenciário Atingido" in response.text
    assert "Evolução e Variação Salarial" in response.text
    assert "Competências e Remunerações" in response.text
    assert "03/2023" in response.text
    assert "7.500,00" in response.text


def test_servico_analytics_calcula_metricas_e_curva() -> None:
    """Testa unitariamente construir_painel_analise e formatar_moeda_br."""
    # Arrange
    contribuicoes = [
        Contribuicao(data_competencia="01/2022", valor=2000.0),
        Contribuicao(data_competencia="02/2022", valor=4000.0),
        Contribuicao(data_competencia="03/2022", valor=7000.0),
    ]

    # Act
    painel = construir_painel_analise(contribuicoes)
    moeda = formatar_moeda_br(painel.maior_remuneracao)

    # Assert
    assert painel.total_competencias == 3
    assert painel.maior_remuneracao == 7000.0
    assert painel.competencia_maior == "03/2022"
    assert painel.atingiu_teto_count == 1
    assert painel.variacao_geral_pct == 250.0
    assert moeda == "7.000,00"
    assert "M " in painel.grafico.caminho_linha
    assert len(painel.itens_tabela) == 3


def test_extrair_html_rejeita_arquivo_nao_pdf(
    client_with_user: tuple[TestClient, Advogado],
) -> None:
    """Verifica se /cnis/extrair-html devolve erro amigável para não-PDFs."""
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
    """Garante que erro no login via navegador redireciona para /login?erro=..."""
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
    assert (
        response.headers.get("location")
        == "/login?erro=Email+ou+senha+incorretos."
    )


def test_tela_login_renderiza_mensagem_de_erro_em_modo_escuro() -> None:
    """Verifica se a rota /login exibe o banner de erro e tema escuro."""
    # Arrange & Act
    with TestClient(app) as client:
        response = client.get("/login?erro=Credenciais+invalidas")

    # Assert
    assert response.status_code == 200
    assert "Credenciais invalidas" in response.text
    assert "Automatize a extração de CNIS com precisão" in response.text
    assert "parse-logo-vazada-branca.png" in response.text
    assert "#1e1e1e" in response.text


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
    """Verifica que o acesso à rota raiz / com sessão vai para /dashboard."""
    # Arrange
    client, _ = client_with_user

    # Act
    response = client.get("/", follow_redirects=False)

    # Assert
    assert response.status_code == 303
    assert response.headers.get("location") == "/dashboard"
