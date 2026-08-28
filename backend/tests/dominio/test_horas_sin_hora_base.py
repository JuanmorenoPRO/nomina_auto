"""Alarma: horas no-extra por encima de lo que el salario cubre.

El tiempo ordinario se paga como presupuesto fijo (`horas_quincena`), no por lo
trabajado. Si la estrategia de extras deja más horas no-extra de las que ese
presupuesto —y el día 31— cubren, esas horas cobran su recargo pero no su hora
base; una ordinaria diurna por encima del tope no cobra nada. No falla nada y
hasta ahora nada lo avisaba.
"""

from datetime import date, time
from decimal import Decimal

from nomina.dominio.entidades.turno import Turno
from nomina.dominio.servicios.calculadora import liquidar
from nomina.dominio.servicios.calendario_festivos import CalendarioFestivos
from nomina.dominio.servicios.clasificador_extras import clasificar_extras
from nomina.dominio.servicios.segmentador import segmentar_turnos
from nomina.semilla import parametros_semilla

PARAMETROS = parametros_semilla()
CALENDARIO = CalendarioFestivos()
SALARIO = Decimal("1750905")
INICIO = date(2026, 8, 16)  # presupuesto 105 h


def _liquidar(turnos, estrategia, **kwargs):
    tramos = segmentar_turnos(turnos, PARAMETROS, CALENDARIO)
    clasificados = clasificar_extras(tramos, PARAMETROS, INICIO, estrategia=estrategia)
    return liquidar(clasificados, SALARIO, PARAMETROS, INICIO, **kwargs)


def _turnos_de_ocho(dias):
    """Turnos diurnos de 8 h: con umbral por turno ninguno genera extra."""
    return [Turno(date(2026, 8, d), time(6), time(14)) for d in dias]


def test_una_quincena_normal_no_dispara_la_alarma():
    # 12 turnos × 8 h = 96 h no-extra, por debajo de las 105 del presupuesto.
    liq = _liquidar(_turnos_de_ocho(range(16, 28)), "jornada")
    assert liq.minutos_sin_hora_base == 0


def test_avisa_cuando_lo_no_extra_pasa_el_presupuesto():
    # 15 turnos × 8 h = 120 h, todas no-extra con umbral por turno. El salario
    # solo paga 105 → 15 h trabajadas sin hora base.
    liq = _liquidar(_turnos_de_ocho(range(16, 31)), "jornada")
    assert liq.minutos_sin_hora_base == 15 * 60


def test_el_dia_31_amplia_lo_que_cubre_el_salario():
    """Las horas del 31 se pagan en su propia línea, así que no son un descubierto."""
    turnos = _turnos_de_ocho(range(16, 32))  # 16 turnos × 8 h = 128 h
    sin_marca = _liquidar(turnos, "jornada")
    con_marca = _liquidar(turnos, "jornada", pagar_dia_31=True)
    assert sin_marca.minutos_sin_hora_base == 23 * 60
    assert con_marca.minutos_sin_hora_base == 15 * 60  # las 8 h del 31 ya se pagan


def test_la_estrategia_semanal_reduce_el_descubierto():
    """Mismo horario: el tope de 42 h/semana manda al lado extra lo que el
    umbral por turno dejaba como ordinario sin base que lo pagara."""
    turnos = _turnos_de_ocho(range(16, 31))
    assert _liquidar(turnos, "jornada").minutos_sin_hora_base == 15 * 60
    assert _liquidar(turnos, "semanal_legal").minutos_sin_hora_base == 0


def test_la_alarma_no_cambia_ningun_valor_liquidado():
    turnos = _turnos_de_ocho(range(16, 31))
    liq = _liquidar(turnos, "jornada")
    assert liq.minutos_sin_hora_base > 0
    # El tiempo ordinario sigue siendo el presupuesto de la quincena, ni más ni menos.
    ordinario = next(c for c in liq.conceptos if c.codigo == "tiempo_ordinario")
    assert float(ordinario.horas) == 105.0
