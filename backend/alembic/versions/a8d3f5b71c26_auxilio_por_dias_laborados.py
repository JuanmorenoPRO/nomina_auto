"""auxilio por días laborados en ajuste_quincena

Marca por empleado y periodo: el auxilio de transporte se prorratea sobre los días
con turno en la quincena (mensual / 30 × días) en vez de pagarse quincenal plano.
Pensada para quien solo alcanzó a trabajar parte de la quincena.

Revision ID: a8d3f5b71c26
Revises: e5c1a7f30b94
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "a8d3f5b71c26"
down_revision: str | None = "e5c1a7f30b94"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "ajuste_quincena",
        sa.Column(
            "auxilio_por_dias_laborados",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
    )


def downgrade() -> None:
    op.drop_column("ajuste_quincena", "auxilio_por_dias_laborados")
