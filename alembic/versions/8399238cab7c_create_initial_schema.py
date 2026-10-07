"""create initial schema

Revision ID: 8399238cab7c
Revises:
Create Date: 2026-10-06 16:36:04.110295

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "8399238cab7c"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "advogados",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("nome", sa.String(length=255), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("senha_hash", sa.String(length=255), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_advogados_email"), "advogados", ["email"], unique=True)

    op.create_table(
        "clientes",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("advogado_id", sa.Uuid(), nullable=False),
        sa.Column("nome", sa.String(length=255), nullable=False),
        sa.Column("cpf", sa.String(length=14), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["advogado_id"],
            ["advogados.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_clientes_advogado_id"),
        "clientes",
        ["advogado_id"],
        unique=False,
    )
    op.create_index(op.f("ix_clientes_cpf"), "clientes", ["cpf"], unique=False)

    op.create_table(
        "extractions_logs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("advogado_id", sa.Uuid(), nullable=False),
        sa.Column("nome_arquivo", sa.String(length=255), nullable=False),
        sa.Column("status", sa.String(length=50), nullable=False),
        sa.Column("mensagem_erro", sa.String(length=1000), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["advogado_id"],
            ["advogados.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_extractions_logs_advogado_id"),
        "extractions_logs",
        ["advogado_id"],
        unique=False,
    )

    op.create_table(
        "contribuicoes",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("cliente_id", sa.Uuid(), nullable=False),
        sa.Column("data_competencia", sa.String(length=10), nullable=False),
        sa.Column("valor", sa.Float(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["cliente_id"],
            ["clientes.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_contribuicoes_cliente_id"),
        "contribuicoes",
        ["cliente_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_contribuicoes_data_competencia"),
        "contribuicoes",
        ["data_competencia"],
        unique=False,
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(
        op.f("ix_contribuicoes_data_competencia"),
        table_name="contribuicoes",
    )
    op.drop_index(
        op.f("ix_contribuicoes_cliente_id"),
        table_name="contribuicoes",
    )
    op.drop_table("contribuicoes")
    op.drop_index(
        op.f("ix_extractions_logs_advogado_id"),
        table_name="extractions_logs",
    )
    op.drop_table("extractions_logs")
    op.drop_index(op.f("ix_clientes_cpf"), table_name="clientes")
    op.drop_index(op.f("ix_clientes_advogado_id"), table_name="clientes")
    op.drop_table("clientes")
    op.drop_index(op.f("ix_advogados_email"), table_name="advogados")
    op.drop_table("advogados")
