"""dias_laborados y dias_incapacidad en liquidacion_empleado

Revision ID: d4b7e2a91c06
Revises: c6a2d9e47f15
Create Date: 2026-11-14 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd4b7e2a91c06'
down_revision: Union[str, Sequence[str], None] = 'c6a2d9e47f15'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema. Nullable: las liquidaciones ya guardadas no tienen el dato."""
    op.add_column("liquidacion_empleado", sa.Column("dias_laborados", sa.Integer(), nullable=True))
    op.add_column("liquidacion_empleado", sa.Column("dias_incapacidad", sa.Integer(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table("liquidacion_empleado") as batch:
        batch.drop_column("dias_incapacidad")
        batch.drop_column("dias_laborados")
