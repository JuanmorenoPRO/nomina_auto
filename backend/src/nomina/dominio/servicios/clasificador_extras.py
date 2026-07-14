"""Clasificación de horas ordinarias vs. extra sobre los tramos de un periodo.

La estrategia es un parámetro con vigencias (`estrategia_clasificacion_extras`):

- `presupuesto_quincenal` (método actual de la contadora): las primeras
  `horas_quincena` (hoy 110 h) del periodo, en orden cronológico, son
  ordinarias; el excedente es extra.
- `semanal_legal`: acumulado por semana calendario (lunes a domingo) contra la
  `jornada_maxima_semanal` vigente en la fecha de cada tramo (44 h → 42 h el
  15-jul-2026). Solo cuenta lo trabajado dentro del periodo liquidado.

Si el umbral cae dentro de un tramo, el tramo se parte en dos; la clasificación
conserva franja y tipo de día (una extra nocturna dominical sigue siéndolo).
"""

from __future__ import annotations

from datetime import date

from nomina.dominio.puertos.parametros import ProveedorParametros
from nomina.dominio.valores.tiempo import MINUTOS_POR_HORA
from nomina.dominio.valores.tramo import Tramo

PRESUPUESTO_QUINCENAL = "presupuesto_quincenal"
SEMANAL_LEGAL = "semanal_legal"


def clasificar_extras(
    tramos: list[Tramo],
    parametros: ProveedorParametros,
    fecha_periodo: date,
    estrategia: str | None = None,
) -> list[Tramo]:
    """Devuelve los tramos (cronológicos) con `es_extra` asignado.

    `fecha_periodo` es la fecha de inicio del periodo: define la vigencia de la
    estrategia y del presupuesto quincenal.
    """
    ordenados = sorted(tramos, key=lambda t: t.inicio)
    estrategia = estrategia or parametros.estrategia_clasificacion_extras(fecha_periodo)
    if estrategia == PRESUPUESTO_QUINCENAL:
        return _por_presupuesto_quincenal(ordenados, parametros, fecha_periodo)
    if estrategia == SEMANAL_LEGAL:
        return _por_semana_legal(ordenados, parametros)
    raise ValueError(f"Estrategia de clasificación desconocida: '{estrategia}'")


def _clasificar_contra_limite(tramo: Tramo, acumulado: int, limite: int) -> list[Tramo]:
    """Parte/marca un tramo según cuánto presupuesto ordinario queda."""
    restante = limite - acumulado
    if restante <= 0:
        return [tramo.como_extra()]
    if tramo.minutos <= restante:
        return [tramo]
    ordinario, extra = tramo.partir_en(restante)
    return [ordinario, extra.como_extra()]


def _por_presupuesto_quincenal(
    tramos: list[Tramo], parametros: ProveedorParametros, fecha_periodo: date
) -> list[Tramo]:
    limite = int(parametros.horas_quincena(fecha_periodo) * MINUTOS_POR_HORA)
    acumulado = 0
    resultado: list[Tramo] = []
    for tramo in tramos:
        resultado.extend(_clasificar_contra_limite(tramo, acumulado, limite))
        acumulado += tramo.minutos
    return resultado


def _por_semana_legal(tramos: list[Tramo], parametros: ProveedorParametros) -> list[Tramo]:
    acumulado_por_semana: dict[tuple[int, int], int] = {}
    resultado: list[Tramo] = []
    for tramo in tramos:
        semana = tramo.fecha.isocalendar()[:2]
        acumulado = acumulado_por_semana.get(semana, 0)
        # la jornada máxima se evalúa en la fecha del tramo (vigencia por fecha)
        limite = int(parametros.jornada_maxima_semanal(tramo.fecha) * MINUTOS_POR_HORA)
        resultado.extend(_clasificar_contra_limite(tramo, acumulado, limite))
        acumulado_por_semana[semana] = acumulado + tramo.minutos
    return resultado
