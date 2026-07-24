"""descuento de seguridad social por unidad y conceptos manuales

Revision ID: c4f1a9b2d7e3
Revises: 7e6140cb7851
Create Date: 2026-07-23 21:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c4f1a9b2d7e3'
down_revision: Union[str, Sequence[str], None] = '7e6140cb7851'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "unidad_residencial",
        sa.Column(
            "descuenta_seguridad_social",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("0"),
        ),
    )
    op.add_column(
        "unidad_residencial",
        sa.Column("config", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
    )
    op.add_column(
        "concepto_liquidado",
        sa.Column(
            "tipo", sa.String(length=12), nullable=False, server_default="devengado"
        ),
    )
    op.create_table(
        "concepto_manual",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("empleado_id", sa.Uuid(), nullable=False),
        sa.Column("periodo_id", sa.Uuid(), nullable=False),
        sa.Column("tipo", sa.String(length=12), nullable=False),
        sa.Column("nombre", sa.String(length=100), nullable=False),
        sa.Column("valor", sa.BigInteger(), nullable=False),
        sa.Column("salarial", sa.Boolean(), nullable=False),
        sa.ForeignKeyConstraint(["empleado_id"], ["empleado.id"]),
        sa.ForeignKeyConstraint(["periodo_id"], ["periodo_liquidacion.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_concepto_manual_empleado_id", "concepto_manual", ["empleado_id"]
    )
    op.create_index(
        "ix_concepto_manual_periodo_id", "concepto_manual", ["periodo_id"]
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index("ix_concepto_manual_periodo_id", table_name="concepto_manual")
    op.drop_index("ix_concepto_manual_empleado_id", table_name="concepto_manual")
    op.drop_table("concepto_manual")
    op.drop_column("concepto_liquidado", "tipo")
    op.drop_column("unidad_residencial", "config")
    op.drop_column("unidad_residencial", "descuenta_seguridad_social")
