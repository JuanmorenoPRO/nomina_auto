"""quincena incompleta por empleado y periodo

Revision ID: 9b1d3f6a7c02
Revises: 1e54e0028299
Create Date: 2026-07-29 00:10:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '9b1d3f6a7c02'
down_revision: Union[str, Sequence[str], None] = '1e54e0028299'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "ajuste_quincena",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("empleado_id", sa.Uuid(), nullable=False),
        sa.Column("periodo_id", sa.Uuid(), nullable=False),
        sa.Column(
            "quincena_incompleta", sa.Boolean(), nullable=False, server_default=sa.text("false")
        ),
        sa.ForeignKeyConstraint(["empleado_id"], ["empleado.id"]),
        sa.ForeignKeyConstraint(["periodo_id"], ["periodo_liquidacion.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("empleado_id", "periodo_id"),
    )
    op.create_index("ix_ajuste_quincena_empleado_id", "ajuste_quincena", ["empleado_id"])
    op.create_index("ix_ajuste_quincena_periodo_id", "ajuste_quincena", ["periodo_id"])


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index("ix_ajuste_quincena_periodo_id", table_name="ajuste_quincena")
    op.drop_index("ix_ajuste_quincena_empleado_id", table_name="ajuste_quincena")
    op.drop_table("ajuste_quincena")
