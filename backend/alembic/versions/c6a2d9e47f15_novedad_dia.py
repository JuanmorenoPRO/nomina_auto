"""novedad_dia: incapacidad / no laboró en días sin turno

Revision ID: c6a2d9e47f15
Revises: b8d2f61c0a47
Create Date: 2026-11-14 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c6a2d9e47f15'
down_revision: Union[str, Sequence[str], None] = 'b8d2f61c0a47'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "novedad_dia",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("empleado_id", sa.Uuid(), nullable=False),
        sa.Column("fecha", sa.Date(), nullable=False),
        sa.Column("tipo", sa.String(length=12), nullable=False),
        sa.ForeignKeyConstraint(["empleado_id"], ["empleado.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("empleado_id", "fecha"),
    )
    op.create_index(op.f("ix_novedad_dia_empleado_id"), "novedad_dia", ["empleado_id"])
    op.create_index(op.f("ix_novedad_dia_fecha"), "novedad_dia", ["fecha"])


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f("ix_novedad_dia_fecha"), table_name="novedad_dia")
    op.drop_index(op.f("ix_novedad_dia_empleado_id"), table_name="novedad_dia")
    op.drop_table("novedad_dia")
