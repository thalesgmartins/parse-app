"""add multitenant schemas and subscriptions

Revision ID: c3a1f7d9e801
Revises: 94b0a8f7c12d
Create Date: 2026-11-01 20:40:00.000000

"""

import uuid
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy import text

revision: str = "c3a1f7d9e801"
down_revision: str | Sequence[str] | None = "94b0a8f7c12d"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Adiciona suporte a schemas por tenant, Google OAuth e assinaturas Asaas."""
    op.add_column("advogados", sa.Column("schema_name", sa.String(length=80), nullable=True))
    op.add_column("advogados", sa.Column("google_sub", sa.String(length=255), nullable=True))
    op.add_column("advogados", sa.Column("avatar_url", sa.String(length=500), nullable=True))
    op.create_index("ix_advogados_schema_name", "advogados", ["schema_name"], unique=True)
    op.create_index("ix_advogados_google_sub", "advogados", ["google_sub"], unique=True)

    op.create_table(
        "assinaturas",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("advogado_id", sa.Uuid(), nullable=False),
        sa.Column("tier", sa.String(length=50), nullable=False, server_default="trial"),
        sa.Column("status", sa.String(length=30), nullable=False, server_default="active"),
        sa.Column("limite_mensal", sa.Integer(), nullable=False, server_default="3"),
        sa.Column("creditos_consumidos", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("creditos_reservados", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("erros_validacao_hoje", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("data_ultimo_erro", sa.String(length=10), nullable=True),
        sa.Column("asaas_customer_id", sa.String(length=100), nullable=True),
        sa.Column("asaas_subscription_id", sa.String(length=100), nullable=True),
        sa.Column("checkout_url", sa.String(length=500), nullable=True),
        sa.Column("ciclo_fim", sa.DateTime(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["advogado_id"], ["advogados.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_assinaturas_advogado_id", "assinaturas", ["advogado_id"], unique=True)
    op.create_index("ix_assinaturas_tier", "assinaturas", ["tier"], unique=False)
    op.create_index("ix_assinaturas_status", "assinaturas", ["status"], unique=False)
    op.create_index(
        "ix_assinaturas_asaas_subscription_id",
        "assinaturas",
        ["asaas_subscription_id"],
        unique=False,
    )

    op.create_table(
        "eventos_pagamento",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("event_id", sa.String(length=120), nullable=False),
        sa.Column("asaas_payment_id", sa.String(length=120), nullable=True),
        sa.Column("asaas_subscription_id", sa.String(length=120), nullable=True),
        sa.Column("tipo_evento", sa.String(length=80), nullable=False),
        sa.Column("payload_resumo", sa.String(length=1000), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_eventos_pagamento_event_id",
        "eventos_pagamento",
        ["event_id"],
        unique=True,
    )
    op.create_index(
        "ix_eventos_pagamento_asaas_payment_id",
        "eventos_pagamento",
        ["asaas_payment_id"],
        unique=False,
    )
    op.create_index(
        "ix_eventos_pagamento_asaas_subscription_id",
        "eventos_pagamento",
        ["asaas_subscription_id"],
        unique=False,
    )

    bind = op.get_bind()
    if bind.dialect.name != "sqlite":
        rows = bind.execute(text("SELECT id FROM public.advogados")).fetchall()
        for (adv_id,) in rows:
            adv_uuid = adv_id if isinstance(adv_id, uuid.UUID) else uuid.UUID(str(adv_id))
            schema = f"tenant_{adv_uuid.hex}"
            bind.execute(
                text("UPDATE public.advogados SET schema_name = :s WHERE id = :id"),
                {"s": schema, "id": adv_uuid},
            )
            bind.execute(
                text(
                    """
                    INSERT INTO public.assinaturas (
                        id, advogado_id, tier, status, limite_mensal,
                        creditos_consumidos, creditos_reservados, erros_validacao_hoje
                    )
                    VALUES (:sub_id, :adv_id, 'trial', 'active', 3, 0, 0, 0)
                    ON CONFLICT (advogado_id) DO NOTHING
                    """
                ),
                {"sub_id": uuid.uuid4(), "adv_id": adv_uuid},
            )
            bind.execute(text(f'CREATE SCHEMA IF NOT EXISTS "{schema}"'))
            bind.execute(
                text(
                    f"""
                    CREATE TABLE IF NOT EXISTS "{schema}".clientes (
                        id UUID PRIMARY KEY,
                        advogado_id UUID NOT NULL REFERENCES public.advogados(id) ON DELETE CASCADE,
                        nome VARCHAR(255) NOT NULL,
                        cpf VARCHAR(14),
                        created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now() NOT NULL
                    )
                    """
                )
            )
            bind.execute(
                text(
                    f"""
                    CREATE TABLE IF NOT EXISTS "{schema}".extraction_jobs (
                        id UUID PRIMARY KEY,
                        advogado_id UUID NOT NULL REFERENCES public.advogados(id) ON DELETE CASCADE,
                        cliente_id UUID REFERENCES "{schema}".clientes(id) ON DELETE CASCADE,
                        nome_arquivo VARCHAR(255) NOT NULL,
                        status VARCHAR(50) NOT NULL DEFAULT 'pending',
                        total_competencias INTEGER NOT NULL DEFAULT 0,
                        mensagem_erro VARCHAR(1000),
                        caminho_arquivo_temp VARCHAR(500),
                        created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now() NOT NULL,
                        updated_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now() NOT NULL
                    )
                    """
                )
            )
            bind.execute(
                text(
                    f"""
                    CREATE TABLE IF NOT EXISTS "{schema}".contribuicoes (
                        id UUID PRIMARY KEY,
                        cliente_id UUID REFERENCES "{schema}".clientes(id) ON DELETE CASCADE,
                        job_id UUID REFERENCES "{schema}".extraction_jobs(id) ON DELETE SET NULL,
                        data_competencia VARCHAR(10) NOT NULL,
                        valor DOUBLE PRECISION NOT NULL,
                        created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now() NOT NULL,
                        CONSTRAINT "uq_{schema}_cliente_competencia"
                            UNIQUE (cliente_id, data_competencia)
                    )
                    """
                )
            )
            bind.execute(
                text(
                    f"""
                    CREATE TABLE IF NOT EXISTS "{schema}".extractions_logs (
                        id UUID PRIMARY KEY,
                        advogado_id UUID NOT NULL REFERENCES public.advogados(id) ON DELETE CASCADE,
                        nome_arquivo VARCHAR(255) NOT NULL,
                        status VARCHAR(50) NOT NULL,
                        mensagem_erro VARCHAR(1000),
                        created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now() NOT NULL
                    )
                    """
                )
            )
            bind.execute(
                text(
                    f"""
                    INSERT INTO "{schema}".clientes (id, advogado_id, nome, cpf, created_at)
                    SELECT id, advogado_id, nome, cpf, created_at
                    FROM public.clientes
                    WHERE advogado_id = :adv_id
                    ON CONFLICT (id) DO NOTHING
                    """
                ),
                {"adv_id": adv_uuid},
            )
            bind.execute(
                text(
                    f"""
                    INSERT INTO "{schema}".extraction_jobs (
                        id, advogado_id, cliente_id, nome_arquivo, status,
                        total_competencias, mensagem_erro, caminho_arquivo_temp,
                        created_at, updated_at
                    )
                    SELECT
                        id, advogado_id, cliente_id, nome_arquivo, status,
                        total_competencias, mensagem_erro, caminho_arquivo_temp,
                        created_at, updated_at
                    FROM public.extraction_jobs
                    WHERE advogado_id = :adv_id
                    ON CONFLICT (id) DO NOTHING
                    """
                ),
                {"adv_id": adv_uuid},
            )
            bind.execute(
                text(
                    f"""
                    INSERT INTO "{schema}".contribuicoes (
                        id, cliente_id, job_id, data_competencia, valor, created_at
                    )
                    SELECT c.id, c.cliente_id, c.job_id, c.data_competencia, c.valor, c.created_at
                    FROM public.contribuicoes c
                    JOIN public.clientes cl ON cl.id = c.cliente_id
                    WHERE cl.advogado_id = :adv_id
                    ON CONFLICT (id) DO NOTHING
                    """
                ),
                {"adv_id": adv_uuid},
            )
            bind.execute(
                text(
                    f"""
                    INSERT INTO "{schema}".extractions_logs (
                        id, advogado_id, nome_arquivo, status, mensagem_erro, created_at
                    )
                    SELECT id, advogado_id, nome_arquivo, status, mensagem_erro, created_at
                    FROM public.extractions_logs
                    WHERE advogado_id = :adv_id
                    ON CONFLICT (id) DO NOTHING
                    """
                ),
                {"adv_id": adv_uuid},
            )


def downgrade() -> None:
    """Reverte criação de tabelas de assinatura e campos multi-tenant."""
    op.drop_index("ix_eventos_pagamento_asaas_subscription_id", table_name="eventos_pagamento")
    op.drop_index("ix_eventos_pagamento_asaas_payment_id", table_name="eventos_pagamento")
    op.drop_index("ix_eventos_pagamento_event_id", table_name="eventos_pagamento")
    op.drop_table("eventos_pagamento")

    op.drop_index("ix_assinaturas_asaas_subscription_id", table_name="assinaturas")
    op.drop_index("ix_assinaturas_status", table_name="assinaturas")
    op.drop_index("ix_assinaturas_tier", table_name="assinaturas")
    op.drop_index("ix_assinaturas_advogado_id", table_name="assinaturas")
    op.drop_table("assinaturas")

    op.drop_index("ix_advogados_google_sub", table_name="advogados")
    op.drop_index("ix_advogados_schema_name", table_name="advogados")
    op.drop_column("advogados", "avatar_url")
    op.drop_column("advogados", "google_sub")
    op.drop_column("advogados", "schema_name")
