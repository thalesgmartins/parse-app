"""Modelos de dados relacionais utilizando SQLAlchemy 2.0."""

import uuid
from datetime import datetime

from sqlalchemy import Float, ForeignKey, Integer, String, UniqueConstraint, func
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
    schema_name: Mapped[str | None] = mapped_column(
        String(80),
        unique=True,
        index=True,
        nullable=True,
    )
    google_sub: Mapped[str | None] = mapped_column(
        String(255),
        unique=True,
        index=True,
        nullable=True,
    )
    avatar_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())

    assinatura: Mapped["Assinatura | None"] = relationship(
        "Assinatura",
        back_populates="advogado",
        uselist=False,
        cascade="all, delete-orphan",
    )
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
    jobs: Mapped[list["JobExtracao"]] = relationship(
        "JobExtracao",
        back_populates="advogado",
        cascade="all, delete-orphan",
    )


class Assinatura(Base):
    """Controle de plano (tier), quotas mensais e assinatura Asaas do advogado."""

    __tablename__ = "assinaturas"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    advogado_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("advogados.id", ondelete="CASCADE"),
        unique=True,
        index=True,
    )
    tier: Mapped[str] = mapped_column(String(50), default="trial", index=True)
    status: Mapped[str] = mapped_column(String(30), default="active", index=True)
    limite_mensal: Mapped[int] = mapped_column(Integer, default=3)
    creditos_consumidos: Mapped[int] = mapped_column(Integer, default=0)
    creditos_reservados: Mapped[int] = mapped_column(Integer, default=0)
    erros_validacao_hoje: Mapped[int] = mapped_column(Integer, default=0)
    data_ultimo_erro: Mapped[str | None] = mapped_column(String(10), nullable=True)
    asaas_customer_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    asaas_subscription_id: Mapped[str | None] = mapped_column(
        String(100),
        index=True,
        nullable=True,
    )
    checkout_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    ciclo_fim: Mapped[datetime | None] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        server_default=func.now(),
        onupdate=func.now(),
    )

    advogado: Mapped["Advogado"] = relationship(
        "Advogado",
        back_populates="assinatura",
    )


class EventoPagamento(Base):
    """Registro idempotente de notificações de webhook de pagamento."""

    __tablename__ = "eventos_pagamento"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    event_id: Mapped[str] = mapped_column(String(120), unique=True, index=True)
    asaas_payment_id: Mapped[str | None] = mapped_column(
        String(120),
        index=True,
        nullable=True,
    )
    asaas_subscription_id: Mapped[str | None] = mapped_column(
        String(120),
        index=True,
        nullable=True,
    )
    tipo_evento: Mapped[str] = mapped_column(String(80))
    payload_resumo: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())


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
    jobs: Mapped[list["JobExtracao"]] = relationship(
        "JobExtracao",
        back_populates="cliente",
        cascade="all, delete-orphan",
    )


class Contribuicao(Base):
    """Entidade que representa uma competência extraída do extrato CNIS."""

    __tablename__ = "contribuicoes"
    __table_args__ = (
        UniqueConstraint(
            "cliente_id",
            "data_competencia",
            name="uq_contribuicoes_cliente_competencia",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    cliente_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("clientes.id", ondelete="CASCADE"),
        index=True,
        nullable=True,
    )
    job_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("extraction_jobs.id", ondelete="SET NULL"),
        index=True,
        nullable=True,
    )
    data_competencia: Mapped[str] = mapped_column(String(10), index=True)
    valor: Mapped[float] = mapped_column(Float)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())

    cliente: Mapped["Cliente | None"] = relationship(
        "Cliente",
        back_populates="contribuicoes",
    )
    job: Mapped["JobExtracao | None"] = relationship(
        "JobExtracao",
        back_populates="contribuicoes",
    )


class JobExtracao(Base):
    """Fila de processamento assíncrono de extratos CNIS."""

    __tablename__ = "extraction_jobs"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    advogado_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("advogados.id", ondelete="CASCADE"),
        index=True,
    )
    cliente_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("clientes.id", ondelete="CASCADE"),
        index=True,
        nullable=True,
    )
    nome_arquivo: Mapped[str] = mapped_column(String(255))
    status: Mapped[str] = mapped_column(String(50), default="pending", index=True)
    total_competencias: Mapped[int] = mapped_column(default=0)
    mensagem_erro: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    caminho_arquivo_temp: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now(), index=True)
    updated_at: Mapped[datetime] = mapped_column(server_default=func.now(), onupdate=func.now())

    advogado: Mapped["Advogado"] = relationship(
        "Advogado",
        back_populates="jobs",
    )
    cliente: Mapped["Cliente | None"] = relationship(
        "Cliente",
        back_populates="jobs",
    )
    contribuicoes: Mapped[list["Contribuicao"]] = relationship(
        "Contribuicao",
        back_populates="job",
        cascade="all, delete-orphan",
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
