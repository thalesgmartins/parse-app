"""Configurações globais de teste para o ParseApp."""

import os

# Define flag para desativar execuções de rede/migrations durante testes unitários
os.environ["TESTING"] = "1"
os.environ["DATABASE_URL"] = "sqlite:///:memory:"

from collections.abc import Generator

import pytest

from app.database.models import Base
from app.database.session import SessionLocal, engine

Base.metadata.create_all(bind=engine)


@pytest.fixture(autouse=True)
def clean_database() -> Generator[None, None, None]:
    """Limpa todas as tabelas após a execução de cada teste para manter isolamento."""
    yield
    with SessionLocal() as session:
        for table in reversed(Base.metadata.sorted_tables):
            session.execute(table.delete())
        session.commit()
