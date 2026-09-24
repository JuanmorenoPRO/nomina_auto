"""no_devengar_auxilio y no_descontar_seguridad_social en ajuste_quincena

Revision ID: a415fe31b41a
Revises: a4e0c62f18b7
Create Date: 2026-09-23 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a415fe31b41a'
down_revision: Union[str, Sequence[str], None] = 'a4e0c62f18b7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "ajuste_quincena",
        sa.Column(
            "no_devengar_auxilio",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
    )
    op.add_column(
        "ajuste_quincena",
        sa.Column(
            "no_descontar_seguridad_social",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("ajuste_quincena", "no_descontar_seguridad_social")
    op.drop_column("ajuste_quincena", "no_devengar_auxilio")
