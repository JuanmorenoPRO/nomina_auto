"""Vigencias de parámetros que cambian con la reducción de jornada (Ley 2101/2021).

El 15-jul-2026 la jornada máxima baja a 42 h/semana; el divisor de mensualización
de la hora ordinaria baja de 220 a 210 h/mes y el presupuesto quincenal de horas
ordinarias de 110 a 105. El motor resuelve ambos por fecha del periodo.
"""

from datetime import date
from decimal import Decimal

from nomina.dominio.entidades.parametro_legal import (
    ConjuntoParametros,
    ParametroLegal,
    incoherencias_horas_quincena,
)
from nomina.dominio.valores.vigencia import Vigencia
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


def test_el_par_horas_divisor_cuadra_en_toda_la_semilla():
    """Invariante: `divisor_hora_ordinaria == 2 × horas_quincena` siempre.

    El salario quincenal es salario/2 por definición, y el motor lo paga como
    `horas_quincena × (salario / divisor)`. Si el par se descuadra, el tiempo
    ordinario deja de dar salario/2 — que es exactamente el error que se produjo
    al bajar el divisor a 210 sin bajar las horas a 105.
    """
    assert incoherencias_horas_quincena(PARAMETROS) == []


def test_detecta_el_par_descuadrado_y_su_tramo():
    """El caso real: divisor actualizado a 210 pero horas quedadas en 110."""
    descuadrado = ConjuntoParametros(
        parametros=(
            ParametroLegal("horas_quincena", "110", Vigencia(date(2000, 1, 1))),
            ParametroLegal(
                "divisor_hora_ordinaria", "220",
                Vigencia(date(2000, 1, 1), date(2026, 7, 14)),
            ),
            ParametroLegal("divisor_hora_ordinaria", "210", Vigencia(date(2026, 7, 15))),
        )
    )
    (hallazgo,) = incoherencias_horas_quincena(descuadrado)
    # Antes del corte el par sí cuadraba (110/220): solo se reporta desde el 15-jul.
    assert hallazgo.desde == date(2026, 7, 15)
    assert hallazgo.hasta is None
    assert "110" in hallazgo.detalle and "210" in hallazgo.detalle


def test_el_par_corregido_no_reporta_nada():
    """Cerrar las horas el 14-jul y abrir 105 el 15-jul deja el conjunto limpio."""
    corregido = ConjuntoParametros(
        parametros=(
            ParametroLegal(
                "horas_quincena", "110", Vigencia(date(2000, 1, 1), date(2026, 7, 14))
            ),
            ParametroLegal("horas_quincena", "105", Vigencia(date(2026, 7, 15))),
            ParametroLegal(
                "divisor_hora_ordinaria", "220",
                Vigencia(date(2000, 1, 1), date(2026, 7, 14)),
            ),
            ParametroLegal("divisor_hora_ordinaria", "210", Vigencia(date(2026, 7, 15))),
        )
    )
    assert incoherencias_horas_quincena(corregido) == []
