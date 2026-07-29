"""incapacitado en empleado

Revision ID: 1e54e0028299
Revises: c4f1a9b2d7e3
Create Date: 2026-07-29 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '1e54e0028299'
down_revision: Union[str, Sequence[str], None] = 'c4f1a9b2d7e3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "empleado",
        sa.Column(
            "incapacitado",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("empleado", "incapacitado")
