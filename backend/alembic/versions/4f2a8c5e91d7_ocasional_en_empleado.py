"""ocasional en empleado

Revision ID: 4f2a8c5e91d7
Revises: 9b1d3f6a7c02
Create Date: 2026-07-29 01:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '4f2a8c5e91d7'
down_revision: Union[str, Sequence[str], None] = '9b1d3f6a7c02'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "empleado",
        sa.Column(
            "ocasional",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("empleado", "ocasional")
