"""Golden test de la unidad EDIFICIO THUNAPA P.H (mayo 2026, dos quincenas).

Reproduce las 8 hojas de `NOMINA MAYO THUNAPA.xlsx` (4 empleados × 2 quincenas)
con el motor: turnos reconstruidos + estrategia `jornada` + factores legados de
la unidad, sin descuento de seguridad social. Las horas por concepto calzan
EXACTO con el documento en las 8 combinaciones.

Los valores en pesos calzan al peso salvo una diferencia sistemática de 1-2
pesos por quincena: el motor redondea cada concepto por separado
(`ROUND_HALF_UP`, regla del repo), mientras que el Excel solo redondea el total
una vez al final. Ver la nota equivalente en `test_golden_puebla.py`.
"""

from decimal import Decimal

from nomina import thunapa
from nomina.dominio.servicios.calculadora import liquidar
from nomina.dominio.servicios.calendario_festivos import CalendarioFestivos
from nomina.dominio.servicios.clasificador_extras import clasificar_extras
from nomina.dominio.servicios.segmentador import segmentar_turnos
from nomina.semilla import parametros_semilla

PARAMETROS = parametros_semilla()
CALENDARIO = CalendarioFestivos()


def _liquidar(documento: str, periodo: str):
    if periodo == "1_15":
        turnos = thunapa.turnos_1_15_de(documento)
        periodo_inicio = thunapa.PERIODO_1_INICIO
        conceptos_manuales = thunapa.CONCEPTOS_MANUALES_1_15.get(documento, ())
    else:
        turnos = thunapa.turnos_16_31_de(documento)
        periodo_inicio = thunapa.PERIODO_2_INICIO
        conceptos_manuales = thunapa.CONCEPTOS_MANUALES_16_31.get(documento, ())
    tramos = segmentar_turnos(turnos, PARAMETROS, CALENDARIO)
    clasificados = clasificar_extras(
        tramos, PARAMETROS, periodo_inicio, estrategia=thunapa.ESTRATEGIA_EXTRAS
    )
    return liquidar(
        clasificados,
        thunapa.SALARIO_BASICO,
        PARAMETROS,
        periodo_inicio,
        factores_override=thunapa.FACTORES_OVERRIDE,
        conceptos_manuales=conceptos_manuales,
        descontar_seguridad_social=False,
    )


def _horas(liq) -> dict[str, int]:
    return {c.codigo: int(c.horas.to_integral_value()) for c in liq.conceptos if c.minutos}


def test_fredy_1_15():
    liq = _liquidar("71712119", "1_15")
    assert _horas(liq) == {
        "tiempo_ordinario": 110, "festivo_diurno": 13, "extra_diurna": 14,
        "extra_diurna_festiva": 4, "recargo_nocturno": 56, "extra_nocturna": 10,
        "extra_nocturna_festiva": 4, "festivo_nocturno": 7,
    }
    assert int(liq.total_devengado) == 1_881_026  # documento: 1.881.023,56
    assert liq.deducciones[0].codigo == "otra_deduccion"
    assert int(liq.deducciones[0].valor) == 50_000
    assert int(liq.neto_a_pagar) == 1_831_026  # documento: 1.831.023,56


def test_hector_1_15():
    liq = _liquidar("70323354", "1_15")
    assert _horas(liq) == {"tiempo_ordinario": 110, "extra_diurna": 40}
    assert int(liq.total_devengado) == 1_397_934  # documento: 1.397.932,95
    assert liq.neto_a_pagar == liq.total_devengado


def test_juan_pablo_1_15():
    liq = _liquidar("15264412", "1_15")
    assert _horas(liq) == {
        "tiempo_ordinario": 110, "festivo_diurno": 14, "extra_diurna": 16,
        "recargo_nocturno": 11, "extra_nocturna": 4, "festivo_nocturno": 8,
    }
    assert int(liq.total_devengado) == 1_579_789  # documento: 1.579.788,31


def test_johan_lopez_1_15():
    liq = _liquidar("1000569123", "1_15")
    assert _horas(liq) == {
        "tiempo_ordinario": 110, "festivo_diurno": 8, "extra_diurna": 8,
        "recargo_nocturno": 46, "extra_nocturna": 12, "festivo_nocturno": 7,
    }
    assert int(liq.total_devengado) == 1_606_451  # documento: 1.606.449,82


def test_fredy_16_31():
    liq = _liquidar("71712119", "16_31")
    assert _horas(liq) == {
        "tiempo_ordinario": 110, "festivo_diurno": 21, "extra_diurna": 24,
        "recargo_nocturno": 20, "extra_nocturna_festiva": 4, "festivo_nocturno": 7,
    }
    assert int(liq.total_devengado) == 1_791_888  # documento: 1.791.886,58
    assert int(liq.deducciones[0].valor) == 50_000
    assert int(liq.neto_a_pagar) == 1_741_888  # documento: 1.741.886,58


def test_hector_16_31():
    liq = _liquidar("70323354", "16_31")
    assert _horas(liq) == {"tiempo_ordinario": 110, "extra_diurna": 40}
    assert int(liq.total_devengado) == 1_397_934  # documento: 1.397.932,95


def test_juan_pablo_16_31():
    liq = _liquidar("15264412", "16_31")
    assert _horas(liq) == {
        "tiempo_ordinario": 110, "festivo_diurno": 13, "extra_diurna": 19,
        "recargo_nocturno": 38, "extra_nocturna": 11, "extra_nocturna_festiva": 4,
        "festivo_nocturno": 15,
    }
    assert int(liq.total_devengado) == 1_964_591  # documento: 1.964.589,48


def test_johan_lopez_16_31():
    liq = _liquidar("1000569123", "16_31")
    assert _horas(liq) == {
        "tiempo_ordinario": 110, "festivo_diurno": 18, "extra_diurna": 8,
        "recargo_nocturno": 48, "extra_nocturna": 18, "extra_nocturna_festiva": 4,
        "festivo_nocturno": 10,
    }
    assert int(liq.total_devengado) == 1_968_571  # documento: 1.968.568,81


def test_thunapa_sin_descuento_seguridad_social():
    """Thunapa no descuenta SS (SALUD/PENSIÓN en 0 en las 8 hojas del documento)."""
    liq = _liquidar("70323354", "1_15")
    assert liq.deducciones == ()
    assert liq.total_deducciones == Decimal(0)
