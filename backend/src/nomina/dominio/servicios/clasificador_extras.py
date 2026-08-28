"""Clasificación de horas ordinarias vs. extra sobre los tramos de un periodo.

La estrategia es un parámetro con vigencias (`estrategia_clasificacion_extras`):

- `presupuesto_quincenal` (método actual de la contadora): las primeras
  `horas_quincena` (hoy 110 h) del periodo, en orden cronológico, son
  ordinarias; el excedente es extra.
- `semanal_legal` (criterio de la ley: CST art. 159 y 161, Ley 2101/2021):
  acumulado por semana calendario (lunes a domingo) contra la
  `jornada_maxima_semanal` vigente en la fecha de cada tramo (44 h → 42 h el
  15-jul-2026). La semana NO se reinicia en el corte de quincena: los tramos de
  la misma semana que ya se liquidaron en el periodo anterior se pasan como
  `tramos_contexto` y consumen presupuesto sin volver a pagarse. Sin eso, una
  semana partida por el corte recibiría 42 h de presupuesto dos veces.
- `diaria`: umbral por día calendario — lo que exceda `horas_jornada_diaria`
  (hoy 8 h) trabajadas en un mismo día es extra. Un día de 12 h paga 8 h
  ordinarias/recargo y 4 h extra. Ojo: la cola de un turno que cruzó medianoche
  cuenta en el día calendario siguiente.
- `jornada`: umbral por TURNO/jornada continua — cada bloque de trabajo sin
  interrupción (los tramos contiguos, aunque crucen medianoche, son una sola
  jornada) paga sus primeras `horas_jornada_diaria` como ordinarias y el resto
  como extra. Así, un turno sáb 18:00→06:00 paga las últimas horas como extra en
  la madrugada del domingo (extra nocturna dominical). Un descanso entre turnos
  abre una jornada nueva con su propio umbral.

Si el umbral cae dentro de un tramo, el tramo se parte en dos; la clasificación
conserva franja y tipo de día (una extra nocturna dominical sigue siéndolo).

Excepción: los tramos de un turno marcado como «jornada ordinaria» llegan ya
clasificados desde la segmentación y ninguna estrategia los toca — pero sus
minutos sí alimentan el acumulado, porque para eso se registró el turno: para
cuadrar las horas de la quincena.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import date

from nomina.dominio.puertos.parametros import ProveedorParametros
from nomina.dominio.valores.tiempo import MINUTOS_POR_HORA
from nomina.dominio.valores.tramo import Tramo

PRESUPUESTO_QUINCENAL = "presupuesto_quincenal"
SEMANAL_LEGAL = "semanal_legal"
DIARIA = "diaria"
JORNADA = "jornada"


def clasificar_extras(
    tramos: list[Tramo],
    parametros: ProveedorParametros,
    fecha_periodo: date,
    estrategia: str | None = None,
    tramos_contexto: Sequence[Tramo] = (),
) -> list[Tramo]:
    """Devuelve los tramos (cronológicos) con `es_extra` asignado.

    `fecha_periodo` es la fecha de inicio del periodo: define la vigencia de la
    estrategia y del presupuesto quincenal.

    `tramos_contexto` son tramos anteriores al periodo que CONSUMEN presupuesto
    pero no se devuelven ni se liquidan aquí (ya se pagaron en su propia
    quincena). Solo `semanal_legal` los usa: son las horas de la misma semana
    calendario que quedaron al otro lado del corte de quincena. Las demás
    estrategias tienen umbral por turno, por día o por periodo y los ignoran.
    """
    ordenados = sorted(tramos, key=lambda t: t.inicio)
    estrategia = estrategia or parametros.estrategia_clasificacion_extras(fecha_periodo)
    if estrategia == PRESUPUESTO_QUINCENAL:
        return _por_presupuesto_quincenal(ordenados, parametros, fecha_periodo)
    if estrategia == SEMANAL_LEGAL:
        return _por_semana_legal(ordenados, parametros, tramos_contexto)
    if estrategia == DIARIA:
        return _por_jornada_diaria(ordenados, parametros)
    if estrategia == JORNADA:
        return _por_jornada_continua(ordenados, parametros)
    raise ValueError(f"Estrategia de clasificación desconocida: '{estrategia}'")


def _clasificar_contra_limite(tramo: Tramo, acumulado: int, limite: int) -> list[Tramo]:
    """Parte/marca un tramo según cuánto presupuesto ordinario queda."""
    if tramo.jornada_ordinaria:
        return [tramo]  # ya clasificado por el umbral propio del turno
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


def _por_jornada_diaria(tramos: list[Tramo], parametros: ProveedorParametros) -> list[Tramo]:
    acumulado_por_dia: dict[date, int] = {}
    resultado: list[Tramo] = []
    for tramo in tramos:
        acumulado = acumulado_por_dia.get(tramo.fecha, 0)
        # el umbral diario se evalúa en la fecha del tramo (vigencia por fecha)
        limite = int(parametros.horas_jornada_diaria(tramo.fecha) * MINUTOS_POR_HORA)
        resultado.extend(_clasificar_contra_limite(tramo, acumulado, limite))
        acumulado_por_dia[tramo.fecha] = acumulado + tramo.minutos
    return resultado


def _por_jornada_continua(tramos: list[Tramo], parametros: ProveedorParametros) -> list[Tramo]:
    """Umbral por bloque de trabajo continuo: los tramos contiguos (fin de uno =
    inicio del siguiente) forman una jornada, aunque crucen medianoche. Un hueco
    de descanso abre una jornada nueva con su propio umbral."""
    resultado: list[Tramo] = []
    acumulado = 0
    fin_anterior = None
    fecha_jornada: date | None = None
    for tramo in tramos:
        if fin_anterior is None or tramo.inicio != fin_anterior:
            acumulado = 0  # nueva jornada (primer tramo o hueco de descanso)
            fecha_jornada = tramo.fecha
        # el umbral se evalúa con la vigencia de la fecha de inicio de la jornada
        limite = int(parametros.horas_jornada_diaria(fecha_jornada) * MINUTOS_POR_HORA)
        resultado.extend(_clasificar_contra_limite(tramo, acumulado, limite))
        acumulado += tramo.minutos
        fin_anterior = tramo.fin
    return resultado


def _por_semana_legal(
    tramos: list[Tramo],
    parametros: ProveedorParametros,
    tramos_contexto: Sequence[Tramo] = (),
) -> list[Tramo]:
    acumulado_por_semana: dict[tuple[int, int], int] = {}
    # Las horas de la misma semana que ya se liquidaron en la quincena anterior
    # gastan presupuesto primero: son cronológicamente previas a todo el periodo.
    for previo in tramos_contexto:
        semana_previa = previo.fecha.isocalendar()[:2]
        acumulado_por_semana[semana_previa] = (
            acumulado_por_semana.get(semana_previa, 0) + previo.minutos
        )
    resultado: list[Tramo] = []
    for tramo in tramos:
        semana = tramo.fecha.isocalendar()[:2]
        acumulado = acumulado_por_semana.get(semana, 0)
        # la jornada máxima se evalúa en la fecha del tramo (vigencia por fecha)
        limite = int(parametros.jornada_maxima_semanal(tramo.fecha) * MINUTOS_POR_HORA)
        resultado.extend(_clasificar_contra_limite(tramo, acumulado, limite))
        acumulado_por_semana[semana] = acumulado + tramo.minutos
    return resultado
