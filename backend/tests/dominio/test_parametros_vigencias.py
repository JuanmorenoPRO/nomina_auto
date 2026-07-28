"""Vigencias de parámetros que cambian con la reducción de jornada (Ley 2101/2021).

El 15-jul-2026 la jornada máxima baja a 42 h/semana; el divisor de mensualización
de la hora ordinaria baja de 220 a 210 h/mes y el presupuesto quincenal de horas
ordinarias de 110 a 105. El motor resuelve ambos por fecha del periodo.
"""

from datetime import date
from decimal import Decimal

from nomina.semilla import parametros_semilla

PARAMETROS = parametros_semilla()


def test_divisor_hora_ordinaria_baja_220_a_210_el_15_jul_2026():
    assert PARAMETROS.divisor_hora_ordinaria(date(2026, 7, 14)) == Decimal(220)
    assert PARAMETROS.divisor_hora_ordinaria(date(2026, 7, 15)) == Decimal(210)


def test_horas_quincena_baja_110_a_105_el_15_jul_2026():
    assert PARAMETROS.horas_quincena(date(2026, 7, 14)) == Decimal(110)
    assert PARAMETROS.horas_quincena(date(2026, 7, 15)) == Decimal(105)


def test_tarifa_hora_ordinaria_sube_con_el_nuevo_divisor():
    salario = Decimal("1750905")
    tarifa_antes = salario / PARAMETROS.divisor_hora_ordinaria(date(2026, 7, 14))
    tarifa_despues = salario / PARAMETROS.divisor_hora_ordinaria(date(2026, 7, 15))
    assert round(tarifa_antes) == 7959
    assert round(tarifa_despues) == 8338
    assert tarifa_despues > tarifa_antes
