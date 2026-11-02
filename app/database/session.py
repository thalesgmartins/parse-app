"""Gerenciamento de conexões e sessões de banco de dados."""

import uuid
from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.config import DATABASE_URL
from app.database.tenancy import ativar_schema_tenant, resetar_schema_sessao

is_sqlite = DATABASE_URL.startswith("sqlite")
connect_args = {"check_same_thread": False} if is_sqlite else {}

if is_sqlite and ":memory:" in DATABASE_URL:
    engine = create_engine(
        DATABASE_URL,
        connect_args=connect_args,
        poolclass=StaticPool,
    )
else:
    engine = create_engine(
        DATABASE_URL,
        pool_pre_ping=True,
        connect_args=connect_args,
    )


SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
)


def criar_sessao_tenant(
    schema_name: str | None = None,
    advogado_id: uuid.UUID | str | None = None,
) -> Session:
    """Cria uma sessão do SQLAlchemy já isolada no schema do tenant informado.

    Args:
        schema_name: Nome do schema PostgreSQL do tenant (opcional).
        advogado_id: Identificador do advogado para derivar o schema (opcional).

    Returns:
        Sessão configurada para operar no schema do tenant.
    """
    db = SessionLocal()
    if schema_name or advogado_id:
        ativar_schema_tenant(db, schema_name=schema_name, advogado_id=advogado_id)
    return db


def get_db() -> Generator[Session, None, None]:
    """Fornece uma sessão transacional de banco de dados como dependência do FastAPI.

    Yields:
        Session: Sessão ativa do SQLAlchemy.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        resetar_schema_sessao(db)
        db.close()
