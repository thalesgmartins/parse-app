"""create extraction jobs table

Revision ID: 051c381ac3ab
Revises: 8399238cab7c
Create Date: 2026-10-08 13:03:42.184373

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "051c381ac3ab"
down_revision: str | Sequence[str] | None = "8399238cab7c"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "extraction_jobs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("advogado_id", sa.Uuid(), nullable=False),
        sa.Column("cliente_id", sa.Uuid(), nullable=True),
        sa.Column("nome_arquivo", sa.String(length=255), nullable=False),
        sa.Column("status", sa.String(length=50), nullable=False),
        sa.Column("total_competencias", sa.Integer(), nullable=False),
        sa.Column("mensagem_erro", sa.String(length=1000), nullable=True),
        sa.Column("caminho_arquivo_temp", sa.String(length=500), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["advogado_id"], ["advogados.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["cliente_id"], ["clientes.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_extraction_jobs_advogado_id"),
        "extraction_jobs",
        ["advogado_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_extraction_jobs_cliente_id"),
        "extraction_jobs",
        ["cliente_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_extraction_jobs_created_at"),
        "extraction_jobs",
        ["created_at"],
        unique=False,
    )
    op.create_index(
        op.f("ix_extraction_jobs_status"),
        "extraction_jobs",
        ["status"],
        unique=False,
    )
    op.add_column("contribuicoes", sa.Column("job_id", sa.Uuid(), nullable=True))
    op.alter_column(
        "contribuicoes",
        "cliente_id",
        existing_type=sa.UUID(),
        nullable=True,
    )
    op.create_index(
        op.f("ix_contribuicoes_job_id"),
        "contribuicoes",
        ["job_id"],
        unique=False,
    )
    op.create_foreign_key(
        "fk_contribuicoes_job_id",
        "contribuicoes",
        "extraction_jobs",
        ["job_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint("fk_contribuicoes_job_id", "contribuicoes", type_="foreignkey")
    op.drop_index(op.f("ix_contribuicoes_job_id"), table_name="contribuicoes")
    op.alter_column(
        "contribuicoes",
        "cliente_id",
        existing_type=sa.UUID(),
        nullable=False,
    )
    op.drop_column("contribuicoes", "job_id")
    op.drop_index(op.f("ix_extraction_jobs_status"), table_name="extraction_jobs")
    op.drop_index(op.f("ix_extraction_jobs_created_at"), table_name="extraction_jobs")
    op.drop_index(op.f("ix_extraction_jobs_cliente_id"), table_name="extraction_jobs")
    op.drop_index(op.f("ix_extraction_jobs_advogado_id"), table_name="extraction_jobs")
    op.drop_table("extraction_jobs")
