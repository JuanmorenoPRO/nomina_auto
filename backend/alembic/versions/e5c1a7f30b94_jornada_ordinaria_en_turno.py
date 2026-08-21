"""jornada ordinaria en turno

Turno registrado solo para cuadrar las horas de la quincena: sus primeros N
minutos no pagan recargo dominical/festivo ni nocturno. NULL = turno normal.

Revision ID: e5c1a7f30b94
Revises: d7e9b2c4a1f8
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "e5c1a7f30b94"
down_revision: str | None = "d7e9b2c4a1f8"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("turno", sa.Column("minutos_jornada_ordinaria", sa.Integer(), nullable=True))


def downgrade() -> None:
    op.drop_column("turno", "minutos_jornada_ordinaria")
