"""corregir jornada_maxima_semanal 2023/2024 y abrir estrategia semanal_legal

Dos correcciones de parámetros legales que el sembrado no propaga (`sembrar_parametros`
es idempotente POR CÓDIGO: si el código ya existe, no vuelve a mirar las vigencias).

1. `jornada_maxima_semanal`. El cronograma real de la Ley 2101/2021 es 47 h desde el
   15-jul-2023, 46 h desde el 15-jul-2024, 44 h desde el 15-jul-2025 y 42 h desde el
   15-jul-2026. Las bases quedaron con 46 y 45 en los dos primeros escalones. No mueve
   nada de 2026, pero al adoptar la estrategia `semanal_legal` estas filas pasan a ser
   dinero en cualquier reliquidación de 2023-2024.

2. `estrategia_clasificacion_extras`. Era `presupuesto_quincenal` con vigencia abierta
   («las primeras 110 h de la quincena son ordinarias»). Ese presupuesto no es un tope
   de jornada: el divisor de 210 h (42/6 × 30, Concepto MinTrabajo 16177 de 2023) solo
   sirve para hallar el valor de la hora ordinaria. El trabajo suplementario es el que
   excede la jornada ordinaria — 8 h/día y 42 h/semana (CST art. 159 y 161, Ley
   2101/2021) —, así que desde el 15-jul-2026 el default pasa a `semanal_legal`.
   Solo afecta unidades sin `config.estrategia_extras` propio.

Conservadora como `c1b7e40a9f38`: cada corrección solo se aplica si encuentra
exactamente la deriva conocida; si alguien ya ajustó el parámetro a mano, no se toca.

Revision ID: d3b81f6ca427
Revises: b9e4d17c5a30
"""

import uuid
from collections.abc import Sequence
from datetime import date

import sqlalchemy as sa
from alembic import op

revision: str = "d3b81f6ca427"
down_revision: str | None = "b9e4d17c5a30"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

CORTE_42 = date(2026, 7, 15)
FIN_PRESUPUESTO = date(2026, 7, 14)
NORMA_JORNADA = "Ley 2101/2021"
NORMA_ESTRATEGIA = "CST art. 159 y 161; Ley 2101/2021"

# (vigente_desde, valor sembrado por error, valor correcto según la ley)
ESCALONES_JORNADA = [
    (date(2023, 7, 15), "46", "47"),
    (date(2024, 7, 15), "45", "46"),
]

parametro = sa.table(
    "parametro_legal",
    sa.column("id", sa.Uuid()),
    sa.column("codigo", sa.String()),
    sa.column("valor", sa.String()),
    sa.column("vigente_desde", sa.Date()),
    sa.column("vigente_hasta", sa.Date()),
    sa.column("norma", sa.String()),
)


def _filas(conexion, codigo: str) -> list:
    return list(
        conexion.execute(
            sa.select(
                parametro.c.id, parametro.c.valor,
                parametro.c.vigente_desde, parametro.c.vigente_hasta,
            ).where(parametro.c.codigo == codigo)
        )
    )


def _corregir_jornada(conexion, *, hacia_la_ley: bool) -> None:
    filas = _filas(conexion, "jornada_maxima_semanal")
    for desde, sembrado, legal in ESCALONES_JORNADA:
        esperado, nuevo = (sembrado, legal) if hacia_la_ley else (legal, sembrado)
        fila = next(
            (f for f in filas if f.vigente_desde == desde and f.valor == esperado), None
        )
        if fila is None:
            continue
        conexion.execute(
            parametro.update().where(parametro.c.id == fila.id).values(valor=nuevo)
        )


def upgrade() -> None:
    conexion = op.get_bind()
    _corregir_jornada(conexion, hacia_la_ley=True)

    # Estrategia: cerrar la vigencia abierta de `presupuesto_quincenal` y abrir
    # `semanal_legal` desde el 15-jul-2026.
    filas = _filas(conexion, "estrategia_clasificacion_extras")
    if len(filas) != 1:
        return
    (fila,) = filas
    if fila.valor != "presupuesto_quincenal" or fila.vigente_hasta is not None:
        return
    if fila.vigente_desde >= CORTE_42:
        return

    conexion.execute(
        parametro.update()
        .where(parametro.c.id == fila.id)
        .values(vigente_hasta=FIN_PRESUPUESTO)
    )
    conexion.execute(
        parametro.insert().values(
            id=uuid.uuid4(),
            codigo="estrategia_clasificacion_extras",
            valor="semanal_legal",
            vigente_desde=CORTE_42,
            vigente_hasta=None,
            norma=NORMA_ESTRATEGIA,
        )
    )


def downgrade() -> None:
    conexion = op.get_bind()
    _corregir_jornada(conexion, hacia_la_ley=False)

    filas = _filas(conexion, "estrategia_clasificacion_extras")
    if len(filas) != 2:
        return
    vieja = next(
        (f for f in filas
         if f.valor == "presupuesto_quincenal" and f.vigente_hasta == FIN_PRESUPUESTO),
        None,
    )
    nueva = next(
        (f for f in filas
         if f.valor == "semanal_legal" and f.vigente_desde == CORTE_42
         and f.vigente_hasta is None),
        None,
    )
    if vieja is None or nueva is None:
        return
    conexion.execute(parametro.delete().where(parametro.c.id == nueva.id))
    conexion.execute(
        parametro.update().where(parametro.c.id == vieja.id).values(vigente_hasta=None)
    )
