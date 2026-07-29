"""ampliar entidad_id en auditoria

Revision ID: b3f6a1c9d4e2
Revises: 4f2a8c5e91d7
Create Date: 2026-07-29 17:00:00.000000

`marcar_ajuste_quincena` audita con una clave compuesta "empleado_id:periodo_id"
(73 caracteres) — el varchar(40) original (dimensionado para un solo UUID, 36
caracteres) la trunca en Postgres y hace fallar la petición entera (bug real en
producción: el checkbox "no laboró todas las horas" tira 500 al marcarlo).
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b3f6a1c9d4e2'
down_revision: Union[str, Sequence[str], None] = '4f2a8c5e91d7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # batch_alter_table: en SQLite (dev local) recrea la tabla; en Postgres
    # (Railway) emite un ALTER COLUMN directo.
    with op.batch_alter_table("auditoria") as batch_op:
        batch_op.alter_column(
            "entidad_id",
            existing_type=sa.String(length=40),
            type_=sa.String(length=80),
            existing_nullable=False,
        )


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table("auditoria") as batch_op:
        batch_op.alter_column(
            "entidad_id",
            existing_type=sa.String(length=80),
            type_=sa.String(length=40),
            existing_nullable=False,
        )
