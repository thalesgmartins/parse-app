"""Gerenciamento de conexões e sessões de banco de dados."""

from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import DATABASE_URL

engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,
)

SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
)


def get_db() -> Generator[Session, None, None]:
    """Fornece uma sessão transacional de banco de dados como dependência do FastAPI.

    Yields:
        Session: Sessão ativa do SQLAlchemy.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
