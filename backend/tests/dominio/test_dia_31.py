"""Día 31: la hora base que el presupuesto de la quincena no cubre.

La quincena 16–fin de mes se paga SIEMPRE como 15 días (`horas_quincena` =
divisor/30 × 15), tenga el mes 30 o 31. Cuando tiene 31, ese día es un 16.º día
que el salario no cubre: marcado `pagar_dia_31`, sus horas no-extra se reconocen
aparte a hora base. Los recargos y las extras del 31 ya se pagan en sus líneas.

Calibrado contra `JULIO RIO CLARO 2026.xlsx` (WALTER GOMEZ, quincena 16-31 jul
2026): 8 h ordinarias el 31 → `DIA 31 TURNO DIA` = $66.701,14.
"""

from datetime import date, time
from decimal import Decimal

import pytest

from nomina.dominio.entidades.turno import Turno
from nomina.dominio.servicios.calculadora import liquidar
from nomina.dominio.servicios.calendario_festivos import CalendarioFestivos
from nomina.dominio.servicios.clasificador_extras import DIARIA, JORNADA, clasificar_extras
from nomina.dominio.servicios.segmentador import segmentar_turnos
from nomina.semilla import parametros_semilla

PARAMETROS = parametros_semilla()
CALENDARIO = CalendarioFestivos()

SALARIO = Decimal("1750905")
PERIODO = date(2026, 7, 16)  # quincena 16-31 jul 2026: divisor 210, 105 h
HORA_BASE = SALARIO / 210  # 8.337,642857…


def _liquidar(turnos: list[Turno], *, estrategia: str | None = None, **kwargs):
    tramos = segmentar_turnos(turnos, PARAMETROS, CALENDARIO)
    clasificados = clasificar_extras(tramos, PARAMETROS, PERIODO, estrategia=estrategia)
    return liquidar(clasificados, SALARIO, PARAMETROS, PERIODO, **kwargs)


def _concepto(liq, codigo):
    return next((c for c in liq.conceptos if c.codigo == codigo), None)


def test_horas_del_31_se_pagan_a_hora_base():
    """WALTER, 31 jul: 8 h ordinarias diurnas → $66.701,14."""
    turnos = [Turno(date(2026, 7, 31), time(6, 0), time(14, 0))]
    dia_31 = _concepto(_liquidar(turnos, pagar_dia_31=True), "dia_31")
    assert dia_31 is not None
    assert dia_31.horas == 8
    assert dia_31.valor == Decimal("66701")  # 8 × 8.337,642857…
    assert dia_31.factor == Decimal("1")


def test_sin_la_marca_no_hay_linea_y_nada_mas_cambia():
    turnos = [Turno(date(2026, 7, 31), time(6, 0), time(14, 0))]
    sin_marca = _liquidar(turnos)
    con_marca = _liquidar(turnos, pagar_dia_31=True)
    assert _concepto(sin_marca, "dia_31") is None
    assert [(c.codigo, c.valor) for c in sin_marca.conceptos] == [
        (c.codigo, c.valor) for c in con_marca.conceptos if c.codigo != "dia_31"
    ]


def test_las_extras_del_31_no_entran_en_la_linea():
    """31 jul 06:00-17:00 con umbral diario de 8 h: 8 h base + 3 h extra diurna.

    Las 3 h extra ya traen la `hora_base` en su propio factor (×1.25).
    """
    turnos = [Turno(date(2026, 7, 31), time(6, 0), time(17, 0))]
    liq = _liquidar(turnos, estrategia=DIARIA, pagar_dia_31=True)
    assert _concepto(liq, "dia_31").horas == 8
    assert _concepto(liq, "extra_diurna").horas == 3


def test_las_nocturnas_del_31_entran_a_hora_base_y_conservan_su_recargo():
    """Turno 30 jul 20:00 → 31 jul 04:00: al 31 le tocan 4 h nocturnas.

    El recargo nocturno se paga por las 8 h del turno; la hora base, solo por
    las 4 que cayeron el 31.
    """
    turnos = [Turno(date(2026, 7, 30), time(20, 0), time(4, 0))]
    liq = _liquidar(turnos, pagar_dia_31=True)
    assert _concepto(liq, "dia_31").horas == 4
    assert _concepto(liq, "recargo_nocturno").horas == 8


def test_el_nocturno_que_arranca_el_31_entra_completo():
    """FREDY, 31 jul 18:00 → 1 ago 05:00 con umbral de 8 h por turno.

    1 h diurna + 7 h nocturnas ordinarias (5 del 31 + 2 ya del 1.º de agosto) y
    3 h extra nocturnas. El turno se liquida en esta quincena y el presupuesto de
    15 días no lo cubre, así que sus 8 h no-extra van completas a la línea, aunque
    dos hayan cruzado la medianoche. Coincide con la fila del 31 de la planilla.
    """
    turnos = [Turno(date(2026, 7, 31), time(18, 0), time(5, 0))]
    liq = _liquidar(turnos, estrategia=JORNADA, pagar_dia_31=True)
    assert _concepto(liq, "dia_31").horas == 8
    assert _concepto(liq, "dia_31").valor == Decimal("66701")
    assert _concepto(liq, "extra_nocturna").horas == 3


def test_un_mes_de_30_dias_nunca_genera_la_linea():
    """Junio no tiene 31: la marca no puede pagar nada aunque quede encendida."""
    tramos = segmentar_turnos(
        [Turno(date(2026, 6, 30), time(6, 0), time(14, 0))], PARAMETROS, CALENDARIO
    )
    clasificados = clasificar_extras(tramos, PARAMETROS, date(2026, 6, 16))
    liq = liquidar(clasificados, SALARIO, PARAMETROS, date(2026, 6, 16), pagar_dia_31=True)
    assert _concepto(liq, "dia_31") is None


def test_un_turno_de_relleno_el_31_tambien_se_paga():
    """La jornada ordinaria dice «esto lo cubre el salario», y el 31 no lo cubre.

    Caso real: la quincena entera registrada como turnos de relleno de 7 h. Sin
    esto, quien cuadra así sus horas nunca vería la línea del 31.
    """
    turnos = [
        Turno(date(2026, 8, d), time(6, 0), time(13, 0), minutos_jornada_ordinaria=7 * 60)
        for d in range(16, 32)
    ]
    tramos = segmentar_turnos(turnos, PARAMETROS, CALENDARIO)
    clasificados = clasificar_extras(tramos, PARAMETROS, date(2026, 8, 16))
    liq = liquidar(clasificados, SALARIO, PARAMETROS, date(2026, 8, 16), pagar_dia_31=True)
    # 16 días × 7 h = 112 h: el salario paga las 105 del presupuesto y el 31 va aparte.
    assert _concepto(liq, "tiempo_ordinario").horas == 105
    assert _concepto(liq, "dia_31").horas == 7
    assert _concepto(liq, "dia_31").valor == Decimal("58364")  # 7 × 8.337,642857…


def test_la_linea_entra_al_ibc_de_seguridad_social():
    turnos = [Turno(date(2026, 7, 31), time(6, 0), time(14, 0))]
    liq = _liquidar(turnos, pagar_dia_31=True, descontar_seguridad_social=True)
    salariales = sum(c.valor for c in liq.conceptos if c.codigo != "auxilio_transporte")
    salud = next(d for d in liq.deducciones if d.codigo == "aporte_salud")
    assert salud.valor == (salariales * Decimal("0.04")).quantize(Decimal("1"))
    assert salariales == Decimal("875453") + Decimal("66701")


def test_con_quincena_incompleta_las_horas_del_31_no_se_pagan_dos_veces():
    """El tiempo ordinario se paga sobre lo laborado SIN el 31, que va aparte."""
    turnos = [
        Turno(date(2026, 7, 20), time(6, 0), time(14, 0)),
        Turno(date(2026, 7, 31), time(6, 0), time(14, 0)),
    ]
    liq = _liquidar(turnos, pagar_dia_31=True, quincena_completa=False)
    assert _concepto(liq, "tiempo_ordinario").horas == 8
    assert _concepto(liq, "dia_31").horas == 8


def test_el_auxilio_prorrateado_si_cuenta_el_31_como_dia_laborado():
    turnos = [
        Turno(date(2026, 7, 20), time(6, 0), time(14, 0)),
        Turno(date(2026, 7, 31), time(6, 0), time(14, 0)),
    ]
    con = _liquidar(turnos, pagar_dia_31=True, auxilio_prorrateado=True)
    sin = _liquidar(turnos, auxilio_prorrateado=True)
    assert _concepto(con, "auxilio_transporte").valor == _concepto(sin, "auxilio_transporte").valor


@pytest.mark.parametrize("dia", [15, 30])
def test_los_demas_dias_no_generan_la_linea(dia: int):
    turnos = [Turno(date(2026, 7, dia), time(6, 0), time(14, 0))]
    assert _concepto(_liquidar(turnos, pagar_dia_31=True), "dia_31") is None
