"""Modelos de dados relacionais utilizando SQLAlchemy 2.0."""

import uuid
from datetime import datetime

from sqlalchemy import Float, ForeignKey, String, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    """Classe base declarativa para todas as tabelas do SQLAlchemy."""

    pass


class Advogado(Base):
    """Entidade que representa o escritório de advocacia / usuário do sistema."""

    __tablename__ = "advogados"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    nome: Mapped[str] = mapped_column(String(255))
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    senha_hash: Mapped[str] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())

    clientes: Mapped[list["Cliente"]] = relationship(
        "Cliente",
        back_populates="advogado",
        cascade="all, delete-orphan",
    )
    logs: Mapped[list["LogExtracao"]] = relationship(
        "LogExtracao",
        back_populates="advogado",
        cascade="all, delete-orphan",
    )


class Cliente(Base):
    """Entidade que representa o cliente titular do benefício previdenciário."""

    __tablename__ = "clientes"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    advogado_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("advogados.id", ondelete="CASCADE"),
        index=True,
    )
    nome: Mapped[str] = mapped_column(String(255))
    cpf: Mapped[str | None] = mapped_column(String(14), index=True, nullable=True)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())

    advogado: Mapped["Advogado"] = relationship(
        "Advogado",
        back_populates="clientes",
    )
    contribuicoes: Mapped[list["Contribuicao"]] = relationship(
        "Contribuicao",
        back_populates="cliente",
        cascade="all, delete-orphan",
    )


class Contribuicao(Base):
    """Entidade que representa uma competência extraída do extrato CNIS."""

    __tablename__ = "contribuicoes"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    cliente_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("clientes.id", ondelete="CASCADE"),
        index=True,
    )
    data_competencia: Mapped[str] = mapped_column(String(10), index=True)
    valor: Mapped[float] = mapped_column(Float)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())

    cliente: Mapped["Cliente"] = relationship(
        "Cliente",
        back_populates="contribuicoes",
    )


class LogExtracao(Base):
    """Registro de auditoria e status de processamentos de PDFs realizados."""

    __tablename__ = "extractions_logs"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    advogado_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("advogados.id", ondelete="CASCADE"),
        index=True,
    )
    nome_arquivo: Mapped[str] = mapped_column(String(255))
    status: Mapped[str] = mapped_column(String(50))
    mensagem_erro: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())

    advogado: Mapped["Advogado"] = relationship(
        "Advogado",
        back_populates="logs",
    )
