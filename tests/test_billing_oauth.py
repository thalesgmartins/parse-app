"""Testes de integração para Planos/Billing Asaas e Autenticação Google OAuth 2.0."""

from unittest.mock import patch

from fastapi.testclient import TestClient

from app.core.config import ASAAS_WEBHOOK_TOKEN
from app.core.security import create_access_token
from app.database.repository import criar_advogado, obter_advogado_por_email
from app.database.session import SessionLocal
from app.main import app
from app.services.quotas import obter_resumo_quota


def test_fluxo_assinatura_tiers_e_consulta_meu_plano() -> None:
    """Testa a troca entre os 3 tiers comerciais e a consulta de quota via API."""
    # Arrange
    with SessionLocal() as db:
        advogado = criar_advogado(
            db,
            nome="Dr. Assinante",
            email="assinante@escritorio.com",
            senha="senha",
        )
        adv_id = advogado.id
        adv_email = advogado.email

    with TestClient(app) as client:
        token = create_access_token({"sub": str(adv_id), "email": adv_email})
        client.cookies.set("access_token", token)

        # Act: Assina o Tier 2 (Pequeno Escritório - 150 extratos/mês)
        resp_assinar = client.post(
            "/assinaturas/assinar",
            data={"tier": "pequeno_escritorio", "forma_pagamento": "PIX"},
            follow_redirects=False,
        )
        resp_plano = client.get("/assinaturas/meu-plano")

    # Assert
    assert resp_assinar.status_code == 303
    assert "sucesso_plano=" in resp_assinar.headers["location"]
    assert resp_plano.status_code == 200
    dados = resp_plano.json()
    assert dados["tier"] == "pequeno_escritorio"
    assert dados["limite_mensal"] == 150
    assert dados["creditos_restantes"] == 150


def test_webhook_asaas_confirmacao_e_idempotencia() -> None:
    """Garante que o webhook do Asaas valide o token, renove a quota e ignore duplicatas."""
    # Arrange
    with SessionLocal() as db:
        advogado = criar_advogado(
            db,
            nome="Dra. Webhook",
            email="webhook@escritorio.com",
            senha="senha",
        )
        adv_id = str(advogado.id)

    payload_webhook = {
        "id": "evt_asaas_001",
        "event": "PAYMENT_CONFIRMED",
        "payment": {
            "id": "pay_999111",
            "subscription": "sub_888222",
            "status": "CONFIRMED",
            "externalReference": f"{adv_id}:grande_escritorio",
        },
    }

    with TestClient(app) as client:
        # 1. Token inválido deve retornar 401
        resp_negado = client.post(
            "/assinaturas/webhook/asaas",
            json=payload_webhook,
            headers={"asaas-access-token": "token-invalido"},
        )
        assert resp_negado.status_code == 401

        # 2. Token válido processa e ativa o plano Grande Escritório (600 extratos)
        resp_ok = client.post(
            "/assinaturas/webhook/asaas",
            json=payload_webhook,
            headers={"asaas-access-token": ASAAS_WEBHOOK_TOKEN},
        )
        assert resp_ok.status_code == 200
        assert resp_ok.json()["status"] == "processed"

        # 3. Reenvio do mesmo event_id é ignorado com idempotência
        resp_duplicado = client.post(
            "/assinaturas/webhook/asaas",
            json=payload_webhook,
            headers={"asaas-access-token": ASAAS_WEBHOOK_TOKEN},
        )
        assert resp_duplicado.status_code == 200
        assert resp_duplicado.json()["status"] == "ignored_duplicate"

    with SessionLocal() as db:
        resumo = obter_resumo_quota(db, adv_id)
        assert resumo.tier == "grande_escritorio"
        assert resumo.limite_mensal == 600
        assert resumo.status == "active"


def test_callback_google_oauth_provisiona_advogado_e_schema() -> None:
    """Valida o login/cadastro automático via Google OAuth 2.0 com proteção CSRF."""
    # Arrange
    state_nonce = "estado_seguro_teste_123"
    state_cookie = create_access_token({"oauth_state": state_nonce})
    perfil_google_mock = {
        "sub": "google-oauth2-sub-987654321",
        "email": "advogado.google@escritorio.com.br",
        "email_verified": True,
        "name": "Dr. Google OAuth",
        "picture": "https://lh3.googleusercontent.com/a/default-user",
    }

    with (
        patch("app.api.auth._trocar_codigo_por_perfil_google", return_value=perfil_google_mock),
        TestClient(app) as client,
    ):
        client.cookies.set("oauth_state", state_cookie)

        # Act
        resp = client.get(
            f"/auth/google/callback?code=4/codigo_teste&state={state_nonce}",
            follow_redirects=False,
        )

    # Assert
    assert resp.status_code == 303
    assert resp.headers["location"] == "/dashboard"
    assert "access_token" in resp.cookies

    with SessionLocal() as db:
        advogado = obter_advogado_por_email(db, "advogado.google@escritorio.com.br")
        assert advogado is not None
        assert advogado.nome == "Dr. Google OAuth"
        assert advogado.google_sub == "google-oauth2-sub-987654321"
        assert advogado.schema_name == f"tenant_{advogado.id.hex}"
