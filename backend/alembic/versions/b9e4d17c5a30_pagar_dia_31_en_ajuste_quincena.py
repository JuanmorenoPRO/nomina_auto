"""pagar día 31 en ajuste_quincena

Marca por empleado y periodo: la quincena 16–fin de mes se paga siempre como 15 días,
así que en los meses de 31 días ese día queda fuera del presupuesto. Marcada, sus horas
no-extra se reconocen aparte a hora base (concepto `dia_31`).

Revision ID: b9e4d17c5a30
Revises: c1b7e40a9f38
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "b9e4d17c5a30"
down_revision: str | None = "c1b7e40a9f38"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "ajuste_quincena",
        sa.Column(
            "pagar_dia_31",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
    )


def downgrade() -> None:
    op.drop_column("ajuste_quincena", "pagar_dia_31")
