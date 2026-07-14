"""Segmentación de turnos: el corazón del motor de cálculo.

Un turno se parte en tramos homogéneos por cortes sucesivos:
 1. medianoche (día calendario) — de aquí emerge la regla de la contadora:
    «el sábado que amanece festivo cambia a festivo a las 12 de la noche»;
 2. límites de la jornada nocturna vigentes ese día (hoy 19:00 y 06:00);
 3. tipo de día calendario (festivo > dominical > ordinario).

Invariante: la suma de los minutos de los tramos = duración del turno, siempre.
"""

from __future__ import annotations

from datetime import date, datetime, time, timedelta

from nomina.dominio.entidades.turno import Turno
from nomina.dominio.puertos.parametros import ProveedorParametros
from nomina.dominio.servicios.calendario_festivos import CalendarioFestivos
from nomina.dominio.valores.tiempo import BOGOTA
from nomina.dominio.valores.tramo import Franja, Tramo


def _cortes_del_dia(dia: date, parametros: ProveedorParametros) -> list[datetime]:
    """Medianoches y límites de jornada nocturna vigentes ese día."""
    inicio_noct, fin_noct = parametros.jornada_nocturna(dia)
    puntos = [time.min, fin_noct, inicio_noct]
    return [datetime.combine(dia, p, tzinfo=BOGOTA) for p in puntos]


def _franja(momento: datetime, parametros: ProveedorParametros) -> Franja:
    inicio_noct, fin_noct = parametros.jornada_nocturna(momento.date())
    t = momento.time()
    if inicio_noct > fin_noct:  # franja nocturna cruza medianoche, ej. 19:00-06:00
        es_nocturna = t >= inicio_noct or t < fin_noct
    else:
        es_nocturna = inicio_noct <= t < fin_noct
    return Franja.NOCTURNA if es_nocturna else Franja.DIURNA


def segmentar(
    turno: Turno,
    parametros: ProveedorParametros,
    calendario: CalendarioFestivos,
) -> list[Tramo]:
    inicio, fin = turno.intervalo()

    cortes: set[datetime] = {inicio, fin}
    dia = inicio.date()
    while dia <= fin.date():
        cortes.update(c for c in _cortes_del_dia(dia, parametros) if inicio < c < fin)
        dia += timedelta(days=1)

    puntos = sorted(cortes)
    tramos: list[Tramo] = []
    for ini, fn in zip(puntos, puntos[1:]):
        medio = ini + (fn - ini) / 2
        tramos.append(
            Tramo(
                inicio=ini,
                fin=fn,
                franja=_franja(medio, parametros),
                tipo_dia=calendario.tipo_dia(ini.date()),
            )
        )
    return tramos


def segmentar_turnos(
    turnos: list[Turno],
    parametros: ProveedorParametros,
    calendario: CalendarioFestivos,
) -> list[Tramo]:
    """Segmenta todos los turnos de un periodo, en orden cronológico."""
    tramos: list[Tramo] = []
    for turno in sorted(turnos, key=lambda t: t.intervalo()[0]):
        tramos.extend(segmentar(turno, parametros, calendario))
    return tramos
