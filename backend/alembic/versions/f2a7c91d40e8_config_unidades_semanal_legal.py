"""unidades: estrategia semanal_legal y sin factores_override legados

Las 9 unidades se sembraron con `estrategia_extras="jornada"` (8 h por turno
continuo) y la tabla de factores combinados de la planilla de la contadora
(2.0 / 2.1 / 2.5). Ambas cosas se corrigen aquí, y el sembrado no lo hace solo:
`sembrar_*` es idempotente POR NOMBRE y nunca actualiza una unidad ya creada.

- **Estrategia.** El trabajo suplementario es el que excede la jornada ordinaria:
  8 h al día y 42 h a la semana desde el 15-jul-2026 (CST art. 159 y 161, Ley
  2101/2021). `jornada` es la regla del art. 7 de la Ley 1920/2018, propia del
  sector de vigilancia; se estaba aplicando también a aseo y a toderos.
- **Factores.** 2.0 / 2.1 / 2.5 salen de `1 + 0.25 + 0.75`, `1 + 0.75 + 0.35` y
  `1 + 0.75 + 0.75`: llevan dentro el recargo dominical del **75 %**, derogado.
  Desde el 1-jul-2026 el recargo es del 90 % (Ley 2466/2025), así que los factores
  correctos son 2.15 / 2.25 / 2.65 — los que el motor calcula de forma aditiva
  cuando no hay override. El override venía pagando de menos.

Conservadora: solo cambia las unidades que están exactamente en el estado sembrado.
Si alguien ya ajustó la config a mano, esa unidad se deja como está. `conceptos_fijos`
(la cuota de manejo de Puebla) no se toca.

⚠️ Esto NO reliquida nada. Las liquidaciones existentes conservan su snapshot; para
que el cambio se refleje hay que reliquidar los periodos ABIERTOS desde la UI.

Revision ID: f2a7c91d40e8
Revises: d3b81f6ca427
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "f2a7c91d40e8"
down_revision: str | None = "d3b81f6ca427"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

ESTRATEGIA_LEGADA = "jornada"
ESTRATEGIA_LEGAL = "semanal_legal"
FACTORES_LEGADOS = {
    "extra_diurna_festiva": "2.0",
    "extra_nocturna_festiva": "2.5",
    "festivo_nocturno": "2.1",
}

unidad = sa.table(
    "unidad_residencial",
    sa.column("id", sa.Uuid()),
    sa.column("nombre", sa.String()),
    sa.column("config", sa.JSON()),
)


def _migrar(conexion, *, desde: str, hasta: str, factores_esperados: dict, factores_nuevos: dict) -> None:
    filas = conexion.execute(
        sa.select(unidad.c.id, unidad.c.nombre, unidad.c.config)
    ).all()
    for fila in filas:
        config = dict(fila.config or {})
        if config.get("estrategia_extras") != desde:
            continue
        if (config.get("factores_override") or {}) != factores_esperados:
            continue
        config["estrategia_extras"] = hasta
        config["factores_override"] = dict(factores_nuevos)
        conexion.execute(
            unidad.update().where(unidad.c.id == fila.id).values(config=config)
        )


def upgrade() -> None:
    _migrar(
        op.get_bind(),
        desde=ESTRATEGIA_LEGADA,
        hasta=ESTRATEGIA_LEGAL,
        factores_esperados=FACTORES_LEGADOS,
        factores_nuevos={},
    )


def downgrade() -> None:
    _migrar(
        op.get_bind(),
        desde=ESTRATEGIA_LEGAL,
        hasta=ESTRATEGIA_LEGADA,
        factores_esperados={},
        factores_nuevos=FACTORES_LEGADOS,
    )
