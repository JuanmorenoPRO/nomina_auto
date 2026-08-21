"""cerrar horas_quincena=110 el 14-jul-2026 y abrir 105 desde el 15-jul-2026

`horas_quincena` y `divisor_hora_ordinaria` son un par acoplado: el salario quincenal
es `horas_quincena × (salario / divisor)`, que solo da `salario / 2` si
`divisor == 2 × horas_quincena`. Con la jornada de 42 h (Ley 2101/2021, desde el
15-jul-2026) el par correcto es 105/210; antes era 110/220.

En las BD sembradas antes de que la semilla partiera la vigencia, `horas_quincena`
quedó como una sola fila de 110 abierta: `sembrar_parametros` es idempotente POR
CÓDIGO, así que nunca insertó la de 105. Si además se actualizó el divisor a 210 a
mano (que es el caso), el par quedó descuadrado y el tiempo ordinario se liquidó de
más (110 h en vez de 105) en todo periodo que empiece desde el 15-jul-2026.

Migración de datos, deliberadamente conservadora: solo corrige cuando encuentra
exactamente esa deriva. Si el parámetro ya está bien, o si alguien creó a mano una
vigencia que arranca en/después del 15-jul-2026, no toca nada — no se pisa una
decisión del usuario.

Revision ID: c1b7e40a9f38
Revises: a8d3f5b71c26
"""

import uuid
from collections.abc import Sequence
from datetime import date

import sqlalchemy as sa
from alembic import op

revision: str = "c1b7e40a9f38"
down_revision: str | None = "a8d3f5b71c26"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

CORTE = date(2026, 7, 15)
FIN_ANTERIOR = date(2026, 7, 14)
NORMA = "práctica contadora (jornada 42 h, Ley 2101/2021)"

# Tabla ligera: el INSERT pasa por los tipos de SQLAlchemy para que el UUID sirva
# igual en SQLite (CHAR(32)) que en Postgres (uuid nativo).
parametro = sa.table(
    "parametro_legal",
    sa.column("id", sa.Uuid()),
    sa.column("codigo", sa.String()),
    sa.column("valor", sa.String()),
    sa.column("vigente_desde", sa.Date()),
    sa.column("vigente_hasta", sa.Date()),
    sa.column("norma", sa.String()),
)


def _filas(conexion) -> list:
    return list(
        conexion.execute(
            sa.select(
                parametro.c.id, parametro.c.valor,
                parametro.c.vigente_desde, parametro.c.vigente_hasta,
            ).where(parametro.c.codigo == "horas_quincena")
        )
    )


def upgrade() -> None:
    conexion = op.get_bind()
    filas = _filas(conexion)
    # Solo la deriva conocida: una única vigencia de 110 sin cerrar.
    if len(filas) != 1:
        return
    (fila,) = filas
    if fila.valor != "110" or fila.vigente_hasta is not None:
        return
    if fila.vigente_desde >= CORTE:
        return

    conexion.execute(
        parametro.update()
        .where(parametro.c.id == fila.id)
        .values(vigente_hasta=FIN_ANTERIOR)
    )
    conexion.execute(
        parametro.insert().values(
            id=uuid.uuid4(),
            codigo="horas_quincena",
            valor="105",
            vigente_desde=CORTE,
            vigente_hasta=None,
            norma=NORMA,
        )
    )


def downgrade() -> None:
    conexion = op.get_bind()
    filas = _filas(conexion)
    # Solo revertir el estado que dejó el upgrade: 110 cerrada el 14-jul + 105 abierta.
    if len(filas) != 2:
        return
    vieja = next(
        (f for f in filas if f.valor == "110" and f.vigente_hasta == FIN_ANTERIOR), None
    )
    nueva = next(
        (f for f in filas
         if f.valor == "105" and f.vigente_desde == CORTE and f.vigente_hasta is None),
        None,
    )
    if vieja is None or nueva is None:
        return

    conexion.execute(parametro.delete().where(parametro.c.id == nueva.id))
    conexion.execute(
        parametro.update().where(parametro.c.id == vieja.id).values(vigente_hasta=None)
    )
