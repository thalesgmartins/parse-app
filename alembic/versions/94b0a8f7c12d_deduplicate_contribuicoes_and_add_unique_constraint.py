"""deduplicate contribuicoes and add unique constraint

Revision ID: 94b0a8f7c12d
Revises: 051c381ac3ab
Create Date: 2026-10-09 00:30:00.000000

"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "94b0a8f7c12d"
down_revision: str | Sequence[str] | None = "051c381ac3ab"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema: deduplica registros e adiciona constraint de unicidade."""
    # Remove registros duplicados existentes mantendo o mais recente por cliente e competencia
    op.execute(
        """
        DELETE FROM contribuicoes
        WHERE id IN (
            SELECT id FROM (
                SELECT id, ROW_NUMBER() OVER (
                    PARTITION BY cliente_id, data_competencia
                    ORDER BY created_at DESC, id DESC
                ) as rn
                FROM contribuicoes
                WHERE cliente_id IS NOT NULL
            ) sub
            WHERE sub.rn > 1
        );
        """
    )

    op.create_unique_constraint(
        "uq_contribuicoes_cliente_competencia",
        "contribuicoes",
        ["cliente_id", "data_competencia"],
    )


def downgrade() -> None:
    """Downgrade schema: remove constraint de unicidade."""
    op.drop_constraint(
        "uq_contribuicoes_cliente_competencia",
        "contribuicoes",
        type_="unique",
    )
