"""dias_no_remunerados en ajuste_quincena

Revision ID: b8d2f61c0a47
Revises: a415fe31b41a
Create Date: 2026-10-30 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b8d2f61c0a47'
down_revision: Union[str, Sequence[str], None] = 'a415fe31b41a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "ajuste_quincena",
        sa.Column(
            "dias_no_remunerados",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
        ),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("ajuste_quincena", "dias_no_remunerados")
