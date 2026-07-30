"""sin_extras en ajuste_quincena

Revision ID: d7e9b2c4a1f8
Revises: b3f6a1c9d4e2
Create Date: 2026-07-30 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd7e9b2c4a1f8'
down_revision: Union[str, Sequence[str], None] = 'b3f6a1c9d4e2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "ajuste_quincena",
        sa.Column(
            "sin_extras",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("ajuste_quincena", "sin_extras")
