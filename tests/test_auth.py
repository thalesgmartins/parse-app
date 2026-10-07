"""Testes de integração para as rotas de autenticação."""

from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.database.models import Base
from app.database.session import get_db
from app.main import app


@pytest.fixture
def client_with_db() -> Generator[TestClient, None, None]:
    """Fornece um TestClient com banco SQLite em memória isolado."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    session_factory = sessionmaker(bind=engine)

    def override_get_db() -> Generator[Session, None, None]:
        session = session_factory()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_db] = override_get_db

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.clear()
    Base.metadata.drop_all(bind=engine)


def test_fluxo_registro_e_login(client_with_db: TestClient) -> None:
    """Testa cadastro de novo advogado e login subsequente."""
    # 1. Registrar advogado
    res_reg = client_with_db.post(
        "/auth/register",
        data={"nome": "Dr. Carlos", "email": "carlos@teste.com", "password": "senha12345"},
        follow_redirects=False,
    )
    assert res_reg.status_code == 303
    assert "access_token" in res_reg.cookies

    # 2. Login com credenciais válidas
    res_login = client_with_db.post(
        "/auth/login",
        data={"email": "carlos@teste.com", "password": "senha12345"},
        follow_redirects=False,
    )
    assert res_login.status_code == 303
    assert "access_token" in res_login.cookies

    # 3. Login com senha errada
    res_falha = client_with_db.post(
        "/auth/login",
        data={"email": "carlos@teste.com", "password": "senhaIncorreta"},
        follow_redirects=False,
    )
    assert res_falha.status_code == 401

    # 4. Logout
    res_logout = client_with_db.get("/auth/logout", follow_redirects=False)
    assert res_logout.status_code == 303
