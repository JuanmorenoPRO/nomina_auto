"""Turnos REALES de EDIFICIO PUEBLA P.H en agosto de 2026 (las dos quincenas).

A diferencia de `puebla.py`, `julio_1_15.py` o `rio_claro_16_31.py`, estos turnos
no están reconstruidos: son los que hay registrados en producción, leídos de la
tabla `turno`. Por eso este módulo sirve para fijar el comportamiento del motor
sobre datos de verdad, no para reproducir una planilla.

Es el caso que destapó el criterio de extras. La contadora liquidó agosto a mano
cuadrando las horas no-extra a exactamente 105 por quincena y repartiendo el
sobrante en unas noches concretas; su neto para MARIA en la 16–31 fue
$1.945.363 contra $1.795.019 del motor. Ni uno ni otro estaba aplicando la ley:

- Las 105 h salen del divisor de mensualización (210 h = 42/6 × 30, Concepto
  MinTrabajo 16177 de 2023), que sirve para hallar el valor de la hora ordinaria
  y no es un tope de jornada. El trabajo suplementario es el que excede la
  jornada ordinaria — 8 h/día y 42 h/semana desde el 15-jul-2026 (CST art. 159
  y 161, Ley 2101/2021) — y no se puede promediar ni reubicar.
- Los turnos del 24 al 27 son de 22:00 a 06:00: **8 h exactas**, sin
  suplementario bajo ninguna regla de umbral. La contadora les cargó 14 h extra.
- Los factores combinados de la unidad (2.0 / 2.1 / 2.5) llevan dentro el
  recargo dominical del 75 %, derogado; con el 90 % vigente son 2.15 / 2.25 / 2.65.

Se incluye la última semana de julio porque `semanal_legal` la necesita: la semana
lunes 27-jul – domingo 2-ago queda partida por el corte de quincena y su
presupuesto de 42 h se gasta primero al otro lado del corte.

Corregido el 27-ago-2026: el turno de WILMAR del 17-ago (22:00→06:00) tenía la marca
de jornada ordinaria (420 min), que le suprimía los recargos de un turno que la
contadora sí liquidó con ellos (nocturno 6 h + nocturno festivo 2 h). La marca del
7-ago (06:00→13:00, 7 h) SÍ se conserva: ese turno es relleno para cuadrar la
quincena, no trabajo real, y su fila en la planilla cuadra exacto (119 h = 119 h).

Ver `tests/dominio/golden/test_golden_puebla_agosto.py` y
`docs/reconciliacion-puebla-agosto-2026.md`.
"""

from __future__ import annotations

from datetime import date, time, timedelta

from nomina.dominio.entidades.turno import Turno
from nomina.puebla import CUOTA_MANEJO, FACTORES_OVERRIDE, NIT, NOMBRE_UNIDAD, SALARIO_BASICO

__all__ = [
    "CUOTA_MANEJO",
    "FACTORES_OVERRIDE",
    "MARIA",
    "NIT",
    "NOMBRE_UNIDAD",
    "PAGA_DIA_31",
    "PRIMERA_QUINCENA",
    "SALARIO_BASICO",
    "SEGUNDA_QUINCENA",
    "WILMAR",
    "turnos_de",
    "turnos_semana_previa",
]

MARIA = "43623487"
WILMAR = "71726091"

PRIMERA_QUINCENA = (date(2026, 8, 1), date(2026, 8, 15))
SEGUNDA_QUINCENA = (date(2026, 8, 16), date(2026, 8, 31))

# Ambos empleados tienen marcada `pagar_dia_31` en la quincena 16–31.
PAGA_DIA_31 = frozenset({MARIA, WILMAR})

# Agosto de 2026: domingos 2, 9, 16, 23 y 30; festivos el 7 (Batalla de Boyacá) y
# el 17 (Asunción, trasladada del sábado 15 por la Ley Emiliani).

# (fecha, hora_inicio, hora_fin, minutos_jornada_ordinaria).
# hora_fin <= hora_inicio ⇒ el turno cruza medianoche. El 4.º campo marca los
# turnos de relleno («esto lo cubre el salario»), tal como están en producción.
TURNOS: dict[str, list[tuple[date, int, int, int | None]]] = {
    MARIA: [
        (date(2026, 7, 27), 14, 22, None), (date(2026, 7, 28), 14, 22, None),
        (date(2026, 7, 29), 14, 22, None), (date(2026, 7, 30), 14, 22, None),
        (date(2026, 7, 31), 6, 18, None),
        (date(2026, 8, 2), 18, 6, None), (date(2026, 8, 3), 22, 6, None),
        (date(2026, 8, 4), 22, 6, None), (date(2026, 8, 5), 22, 6, None),
        (date(2026, 8, 6), 22, 6, None), (date(2026, 8, 7), 18, 6, None),
        (date(2026, 8, 8), 18, 6, None), (date(2026, 8, 10), 6, 14, None),
        (date(2026, 8, 11), 6, 14, None), (date(2026, 8, 12), 6, 14, None),
        (date(2026, 8, 13), 6, 14, None), (date(2026, 8, 15), 6, 18, None),
        (date(2026, 8, 16), 6, 18, None), (date(2026, 8, 17), 14, 22, None),
        (date(2026, 8, 18), 14, 22, None), (date(2026, 8, 19), 14, 22, None),
        (date(2026, 8, 20), 14, 22, None), (date(2026, 8, 21), 6, 18, None),
        (date(2026, 8, 23), 18, 6, None), (date(2026, 8, 24), 22, 6, None),
        (date(2026, 8, 25), 22, 6, None), (date(2026, 8, 26), 22, 6, None),
        (date(2026, 8, 27), 22, 6, None), (date(2026, 8, 28), 18, 6, None),
        (date(2026, 8, 29), 18, 6, None), (date(2026, 8, 31), 6, 14, None),
    ],
    WILMAR: [
        (date(2026, 7, 27), 22, 6, None), (date(2026, 7, 28), 22, 6, None),
        (date(2026, 7, 29), 22, 6, None), (date(2026, 7, 30), 22, 6, None),
        (date(2026, 7, 31), 18, 6, None),
        (date(2026, 8, 1), 18, 6, None), (date(2026, 8, 3), 6, 14, None),
        (date(2026, 8, 4), 6, 14, None), (date(2026, 8, 5), 6, 14, None),
        (date(2026, 8, 6), 6, 14, None), (date(2026, 8, 7), 6, 13, 420),
        (date(2026, 8, 8), 6, 18, None), (date(2026, 8, 9), 6, 18, None),
        (date(2026, 8, 10), 14, 22, None), (date(2026, 8, 11), 14, 22, None),
        (date(2026, 8, 12), 14, 22, None), (date(2026, 8, 13), 14, 22, None),
        (date(2026, 8, 14), 6, 18, None),
        (date(2026, 8, 16), 18, 6, None), (date(2026, 8, 17), 22, 6, None),
        (date(2026, 8, 18), 22, 6, None), (date(2026, 8, 19), 22, 6, None),
        (date(2026, 8, 20), 22, 6, None), (date(2026, 8, 21), 18, 6, None),
        (date(2026, 8, 22), 18, 6, None), (date(2026, 8, 24), 6, 14, None),
        (date(2026, 8, 25), 6, 14, None), (date(2026, 8, 26), 6, 14, None),
        (date(2026, 8, 27), 6, 14, None), (date(2026, 8, 29), 6, 18, None),
        (date(2026, 8, 30), 6, 18, None), (date(2026, 8, 31), 14, 22, None),
    ],
}


def _entre(documento: str, desde: date, hasta: date) -> list[Turno]:
    return [
        Turno(
            fecha=fecha,
            hora_inicio=time(inicio % 24),
            hora_fin=time(fin % 24),
            minutos_jornada_ordinaria=jornada_ordinaria,
        )
        for fecha, inicio, fin, jornada_ordinaria in TURNOS[documento]
        if desde <= fecha <= hasta
    ]


def turnos_de(documento: str, quincena: tuple[date, date]) -> list[Turno]:
    """Turnos del empleado dentro de la quincena, tal como están en producción."""
    return _entre(documento, *quincena)


def turnos_semana_previa(documento: str, quincena: tuple[date, date]) -> list[Turno]:
    """Turnos de la misma semana ISO que quedaron antes del inicio de la quincena.

    Misma ventana que `LiquidarQuincena._tramos_semana_previa`: desde el día
    anterior al lunes de esa semana (para atrapar el turno del domingo que cruza
    medianoche) hasta la víspera del periodo.
    """
    inicio = quincena[0]
    lunes = inicio - timedelta(days=inicio.weekday())
    return _entre(documento, lunes - timedelta(days=1), inicio - timedelta(days=1))
