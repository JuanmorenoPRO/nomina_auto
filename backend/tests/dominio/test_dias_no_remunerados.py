"""Días no remunerados: permiso o licencia sin sueldo dentro de la quincena.

Cada día le quita al presupuesto una jornada de mes comercial (divisor/30 = 7 h
desde el 15-jul-2026) y al auxilio `mensual/30`. No depende de cuántas horas quedaron
como extra, que es justo lo que falla si se usa «quincena incompleta» para esto.

Caso real: RIGOBERTO MARIN, EDIFICIO RIO CLARO P.H, quincena 16-31 oct 2026. Trabajó
128 h (17–23 de 6 a 18, 24–27 de 6 a 14, 29 de 6 a 18), descansó el 16 y el 28 y tuvo
permiso no remunerado el 30 y el 31. Con `semanal_legal` y la semana del 12 ya llena,
solo 70 h quedan no-extra: «quincena incompleta» le pagaba 10 días de salario.
"""

from datetime import date, time
from decimal import ROUND_HALF_UP, Decimal

import pytest

from nomina.dominio.entidades.turno import Turno
from nomina.dominio.servicios.calculadora import liquidar
from nomina.dominio.servicios.calendario_festivos import CalendarioFestivos
from nomina.dominio.servicios.clasificador_extras import SEMANAL_LEGAL, clasificar_extras
from nomina.dominio.servicios.segmentador import segmentar_turnos
from nomina.semilla import parametros_semilla

PARAMETROS = parametros_semilla()
CALENDARIO = CalendarioFestivos()

SALARIO = Decimal("1750905")
PERIODO = date(2026, 10, 16)  # divisor 210, 105 h
HORA_BASE = SALARIO / 210
AUXILIO_MENSUAL = PARAMETROS.auxilio_transporte_mensual(PERIODO)

TURNOS_RIGOBERTO = (
    [Turno(date(2026, 10, d), time(6), time(18)) for d in range(17, 24)]
    + [Turno(date(2026, 10, d), time(6), time(14)) for d in (24, 25, 26, 27)]
    + [Turno(date(2026, 10, 29), time(6), time(18))]
)
# Lunes 12 a jueves 15: ya llenan las 42 h de la semana que cruza el corte.
SEMANA_PREVIA = [Turno(date(2026, 10, d), time(6), time(18)) for d in (12, 13, 14, 15)]


def _liquidar(**kwargs):
    tramos = segmentar_turnos(TURNOS_RIGOBERTO, PARAMETROS, CALENDARIO)
    contexto = segmentar_turnos(SEMANA_PREVIA, PARAMETROS, CALENDARIO)
    clasificados = clasificar_extras(
        tramos, PARAMETROS, PERIODO, estrategia=SEMANAL_LEGAL, tramos_contexto=contexto
    )
    return liquidar(clasificados, SALARIO, PARAMETROS, PERIODO, **kwargs)


def _pesos(valor: Decimal) -> Decimal:
    return valor.quantize(Decimal("1"), rounding=ROUND_HALF_UP)


def _concepto(liq, codigo, lineas=None):
    return next(c for c in (lineas or liq.conceptos) if c.codigo == codigo)


@pytest.mark.parametrize("dias, horas", [(0, 105), (1, 98), (2, 91)])
def test_cada_dia_quita_una_jornada_del_tiempo_ordinario(dias, horas):
    ordinario = _concepto(_liquidar(dias_no_remunerados=dias), "tiempo_ordinario")
    assert ordinario.horas == horas
    assert ordinario.valor == _pesos(horas * HORA_BASE)


@pytest.mark.parametrize("dias", [1, 2])
def test_cada_dia_quita_un_treintavo_del_auxilio(dias):
    auxilio = _concepto(_liquidar(dias_no_remunerados=dias), "auxilio_transporte")
    esperado = AUXILIO_MENSUAL / 2 - AUXILIO_MENSUAL * dias / 30
    assert auxilio.valor == _pesos(esperado)


def test_no_toca_extras_ni_recargos():
    sin = _liquidar()
    con = _liquidar(dias_no_remunerados=2)
    ajenos = {"tiempo_ordinario", "auxilio_transporte"}
    assert [(c.codigo, c.valor) for c in sin.conceptos if c.codigo not in ajenos] == [
        (c.codigo, c.valor) for c in con.conceptos if c.codigo not in ajenos
    ]


def test_quincena_incompleta_paga_menos_que_los_dias_no_remunerados():
    """El error del caso real: 70 h no-extra = 10 días de salario en vez de 13."""
    incompleta = _concepto(_liquidar(quincena_completa=False), "tiempo_ordinario")
    permiso = _concepto(_liquidar(dias_no_remunerados=2), "tiempo_ordinario")
    assert incompleta.horas == 70
    assert permiso.horas == 91


def test_baja_el_ibc_de_los_aportes():
    sin = _liquidar(descontar_seguridad_social=True)
    con = _liquidar(descontar_seguridad_social=True, dias_no_remunerados=1)
    ibc = lambda liq: _concepto(liq, "aporte_salud", liq.deducciones).valor / Decimal("0.04")  # noqa: E731
    menos = _concepto(sin, "tiempo_ordinario").valor - _concepto(con, "tiempo_ordinario").valor
    assert menos == _pesos(7 * HORA_BASE)
    assert abs(ibc(sin) - ibc(con) - menos) < 25  # salud se redondea a pesos: ±0,5 / 4 %


def test_los_dias_mandan_sobre_el_auxilio_prorrateado():
    """Caso real en prod: con el prorrateo marcado salían 70 h no-extra = $83.032.
    Con 2 días de permiso el auxilio son 13 días: 249.095 × 13/30 = $107.941."""
    liq = _liquidar(dias_no_remunerados=2, auxilio_prorrateado=True)
    auxilio = _concepto(liq, "auxilio_transporte")
    assert auxilio.valor == _pesos(AUXILIO_MENSUAL * 13 / 30)
    assert auxilio.componentes == {"dias_no_remunerados": Decimal(2)}


def test_sin_dias_el_prorrateo_sigue_igual():
    liq = _liquidar(auxilio_prorrateado=True)
    assert _concepto(liq, "auxilio_transporte").componentes == {"horas_laboradas": Decimal(70)}


def test_quince_dias_de_permiso_no_pagan_ordinario_ni_auxilio():
    liq = _liquidar(dias_no_remunerados=15, auxilio_prorrateado=True)
    assert _concepto(liq, "tiempo_ordinario").horas == 0
    assert _concepto(liq, "auxilio_transporte").valor == 0


@pytest.mark.parametrize("dias", [-1, 16])
def test_fuera_de_rango_es_error(dias):
    with pytest.raises(ValueError, match="Días no remunerados"):
        _liquidar(dias_no_remunerados=dias)
