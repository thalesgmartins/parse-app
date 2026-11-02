"""add_cpf_cnpj_to_advogados

Revision ID: d4e8a2b1c902
Revises: c3a1f7d9e801
Create Date: 2026-11-02 02:55:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision: str = "d4e8a2b1c902"
down_revision: str | Sequence[str] | None = "c3a1f7d9e801"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Adiciona coluna cpf_cnpj na tabela advogados."""
    bind = op.get_bind()
    insp = inspect(bind)
    colunas = {col["name"] for col in insp.get_columns("advogados")}
    if "cpf_cnpj" not in colunas:
        op.add_column(
            "advogados",
            sa.Column("cpf_cnpj", sa.String(length=20), nullable=True),
        )


def downgrade() -> None:
    """Remove coluna cpf_cnpj da tabela advogados."""
    bind = op.get_bind()
    insp = inspect(bind)
    colunas = {col["name"] for col in insp.get_columns("advogados")}
    if "cpf_cnpj" in colunas:
        op.drop_column("advogados", "cpf_cnpj")
