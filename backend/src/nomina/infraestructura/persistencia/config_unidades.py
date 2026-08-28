"""Configuración de cálculo VIGENTE para las unidades que se siembran.

Separada de los módulos de referencia (`nomina.puebla`, `nomina.julio_1_15`,
`nomina.thunapa`, `nomina.rio_claro_16_31`): aquellos congelan la planilla
histórica de la contadora y sus golden tests deben seguir reproduciéndola al
peso; esto es lo que va a producción hoy.

Dos decisiones, ambas del 27-ago-2026:

- **`semanal_legal`.** El criterio legal de trabajo suplementario es el que
  excede la jornada ordinaria — 8 h al día y 42 h a la semana desde el
  15-jul-2026 (CST art. 159 y 161, Ley 2101/2021) —, no un presupuesto por
  quincena ni un umbral por turno. Antes se sembraba `jornada` (8 h por turno
  continuo), que es la regla del art. 7 de la Ley 1920/2018 para vigilancia:
  legal pero más estrecha, y aplicada a unidades que no son de vigilancia.
- **Sin `factores_override`.** La tabla de factores combinados de la planilla
  (2.0 / 2.1 / 2.5) está armada con el recargo dominical del 75 %, derogado.
  Desde el 1-jul-2026 el recargo es del 90 %, así que los factores correctos son
  2.15 / 2.25 / 2.65 — y el motor ya los calcula así de forma aditiva. El
  override los pisaba con la tabla vieja, en contra del empleado.

La migración `f2a7c91d40e8` propaga estos valores a las bases existentes: el
sembrado es idempotente POR NOMBRE y no actualiza unidades ya creadas.
"""

from __future__ import annotations

from decimal import Decimal

from nomina.dominio.servicios.clasificador_extras import SEMANAL_LEGAL

ESTRATEGIA_EXTRAS_VIGENTE: str = SEMANAL_LEGAL

# Vacío a propósito: el motor calcula los combinados de forma aditiva sobre el
# recargo dominical vigente en la fecha de cada tramo.
FACTORES_OVERRIDE_VIGENTES: dict[str, Decimal] = {}
