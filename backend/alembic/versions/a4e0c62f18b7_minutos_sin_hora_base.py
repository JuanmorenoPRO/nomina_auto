"""alarma: minutos no-extra por encima de lo que cubre el salario

El tiempo ordinario se paga como presupuesto fijo (`horas_quincena`), así que si
la estrategia de extras deja más horas no-extra de las que ese presupuesto y el
día 31 cubren, esas horas cobran su recargo pero no su hora base — y una
ordinaria diurna por encima del tope no cobra nada. No fallaba nada y nada lo
avisaba. Esta columna guarda el excedente para poder mostrarlo en la UI.

Es un dato de diagnóstico, no un valor liquidado: default 0 y las liquidaciones
anteriores quedan en 0 (no se recalculan; conservan su snapshot).

Revision ID: a4e0c62f18b7
Revises: f2a7c91d40e8
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "a4e0c62f18b7"
down_revision: str | None = "f2a7c91d40e8"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "liquidacion_empleado",
        sa.Column("minutos_sin_hora_base", sa.Integer(), nullable=False, server_default="0"),
    )


def downgrade() -> None:
    op.drop_column("liquidacion_empleado", "minutos_sin_hora_base")
