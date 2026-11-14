"""Auxilio de transporte por días: `mensual / 30 × (15 − días que no lo generan)`.

Los días que no generan auxilio son los marcados en el cuadro de turnos como
incapacidad o «no laboró», más los días no remunerados. Los descansos sí cuentan.

Caso real: TORRE LAUREL, empleado incapacitado los 2 últimos días de la quincena →
13 días de auxilio, no 15 (plano) ni 0 (estado `incapacitado` del empleado).
"""

from datetime import date, time
from decimal import ROUND_HALF_UP, Decimal

import pytest

from nomina.dominio.entidades.turno import Turno
from nomina.dominio.servicios.calculadora import liquidar
from nomina.dominio.servicios.calendario_festivos import CalendarioFestivos
from nomina.dominio.servicios.clasificador_extras import clasificar_extras
from nomina.dominio.servicios.segmentador import segmentar_turnos
from nomina.dominio.valores.novedad_dia import INCAPACIDAD, NO_LABORO
from nomina.semilla import parametros_semilla

PARAMETROS = parametros_semilla()
SALARIO = Decimal("1750905")
PERIODO = date(2026, 11, 1)
AUXILIO_MENSUAL = PARAMETROS.auxilio_transporte_mensual(PERIODO)


def _pesos(valor: Decimal) -> Decimal:
    return valor.quantize(Decimal("1"), rounding=ROUND_HALF_UP)


def _auxilio(periodo=PERIODO, turnos=(), **kwargs):
    tramos = segmentar_turnos(list(turnos), PARAMETROS, CalendarioFestivos())
    clasificados = clasificar_extras(tramos, PARAMETROS, periodo)
    liq = liquidar(clasificados, SALARIO, PARAMETROS, periodo, **kwargs)
    return next(c for c in liq.conceptos if c.codigo == "auxilio_transporte")


# Torre Laurel: trabaja del 1 al 13 (con un descanso el domingo 8) y se incapacita el 14 y 15.
TURNOS_LAUREL = [Turno(date(2026, 11, d), time(6), time(14)) for d in range(1, 14) if d != 8]
INCAPACIDAD_LAUREL = {date(2026, 11, 14): INCAPACIDAD, date(2026, 11, 15): INCAPACIDAD}


@pytest.mark.parametrize("casilla", [True, False])
def test_torre_laurel_dos_dias_incapacitado_son_13_dias(casilla):
    """Marcar los días basta: con o sin la casilla, 13 días. El descanso del 8 cuenta."""
    auxilio = _auxilio(
        turnos=TURNOS_LAUREL, auxilio_prorrateado=casilla, dias_sin_auxilio=INCAPACIDAD_LAUREL
    )
    assert auxilio.valor == _pesos(AUXILIO_MENSUAL * 13 / 30)
    assert auxilio.componentes == {"dias_laborados": Decimal(13), "dias_incapacidad": Decimal(2)}


def test_casilla_sin_marcas_es_el_quincenal_plano():
    auxilio = _auxilio(turnos=TURNOS_LAUREL, auxilio_prorrateado=True)
    assert auxilio.valor == _pesos(AUXILIO_MENSUAL / 2)
    assert auxilio.componentes == {"dias_laborados": Decimal(15)}


def test_sin_casilla_ni_marcas_es_el_plano_sin_componentes():
    auxilio = _auxilio(turnos=TURNOS_LAUREL)
    assert auxilio.valor == _pesos(AUXILIO_MENSUAL / 2)
    assert auxilio.componentes == {}


def test_no_laboro_e_incapacidad_y_no_remunerados_se_restan_juntos():
    marcas = {date(2026, 11, 1): NO_LABORO, date(2026, 11, 15): INCAPACIDAD}
    auxilio = _auxilio(dias_sin_auxilio=marcas, dias_no_remunerados=3)
    assert auxilio.valor == _pesos(AUXILIO_MENSUAL * 10 / 30)
    assert auxilio.componentes == {
        "dias_laborados": Decimal(10),
        "dias_incapacidad": Decimal(1),
        "dias_no_laboro": Decimal(1),
        "dias_no_remunerados": Decimal(3),
    }


def test_nunca_baja_de_cero():
    """Si un día se cuenta dos veces (marcado y además como no remunerado), tope en 0."""
    marcas = {date(2026, 11, d): INCAPACIDAD for d in range(1, 16)}
    auxilio = _auxilio(dias_sin_auxilio=marcas, dias_no_remunerados=2)
    assert auxilio.valor == 0
    assert auxilio.componentes["dias_laborados"] == 0


def test_el_31_no_descuenta():
    """La quincena 16–31 vale 15 días: el 31 no se paga, marcarlo no le quita nada."""
    periodo = date(2026, 10, 16)
    marcas = {date(2026, 10, 30): INCAPACIDAD, date(2026, 10, 31): INCAPACIDAD}
    auxilio = _auxilio(periodo=periodo, dias_sin_auxilio=marcas)
    assert auxilio.valor == _pesos(AUXILIO_MENSUAL * 14 / 30)
    assert auxilio.componentes == {"dias_laborados": Decimal(14), "dias_incapacidad": Decimal(1)}


def test_febrero_entero_incapacitado_es_cero():
    """16–28 de febrero son 13 días calendario: marcado el último, la marca cubre
    hasta el 30 comercial, así que la quincena entera incapacitada da 0 y no 2."""
    periodo = date(2027, 2, 16)
    marcas = {date(2027, 2, d): INCAPACIDAD for d in range(16, 29)}
    assert _auxilio(periodo=periodo, dias_sin_auxilio=marcas).valor == 0


def test_febrero_sin_el_ultimo_dia_cuenta_solo_lo_marcado():
    periodo = date(2027, 2, 16)
    marcas = {date(2027, 2, 16): INCAPACIDAD, date(2027, 2, 17): INCAPACIDAD}
    auxilio = _auxilio(periodo=periodo, dias_sin_auxilio=marcas)
    mensual = PARAMETROS.auxilio_transporte_mensual(periodo)
    assert auxilio.valor == _pesos(mensual * 13 / 30)


def test_marcas_no_tocan_el_tiempo_ordinario():
    tramos = segmentar_turnos(TURNOS_LAUREL, PARAMETROS, CalendarioFestivos())
    clasificados = clasificar_extras(tramos, PARAMETROS, PERIODO)
    sin = liquidar(clasificados, SALARIO, PARAMETROS, PERIODO)
    con = liquidar(clasificados, SALARIO, PARAMETROS, PERIODO, dias_sin_auxilio=INCAPACIDAD_LAUREL)
    ordinario = lambda liq: next(c for c in liq.conceptos if c.codigo == "tiempo_ordinario")  # noqa: E731
    assert ordinario(sin) == ordinario(con)


def _liquidacion(**kwargs):
    tramos = segmentar_turnos(TURNOS_LAUREL, PARAMETROS, CalendarioFestivos())
    clasificados = clasificar_extras(tramos, PARAMETROS, PERIODO)
    return liquidar(clasificados, SALARIO, PARAMETROS, PERIODO, **kwargs)


def test_dias_del_comprobante_torre_laurel():
    """INCAPACIDAD / DIAS LAB del comprobante: la misma cuenta del auxilio."""
    liq = _liquidacion(dias_sin_auxilio=INCAPACIDAD_LAUREL)
    assert (liq.dias_incapacidad, liq.dias_laborados) == (2, 13)


def test_dias_del_comprobante_sin_marcas():
    liq = _liquidacion()
    assert (liq.dias_incapacidad, liq.dias_laborados) == (0, 15)


def test_no_laboro_y_no_remunerados_bajan_dias_lab_pero_no_la_incapacidad():
    marcas = {date(2026, 11, 14): INCAPACIDAD, date(2026, 11, 15): NO_LABORO}
    liq = _liquidacion(dias_sin_auxilio=marcas, dias_no_remunerados=1)
    assert (liq.dias_incapacidad, liq.dias_laborados) == (1, 12)


def test_los_dias_se_calculan_aunque_no_se_pague_auxilio():
    """Empleado incapacitado/ocasional o «no devengar»: no hay auxilio, pero el
    comprobante sigue mostrando los días."""
    liq = _liquidacion(dias_sin_auxilio=INCAPACIDAD_LAUREL, incluir_auxilio_transporte=False)
    assert "auxilio_transporte" not in {c.codigo for c in liq.conceptos}
    assert (liq.dias_incapacidad, liq.dias_laborados) == (2, 13)


def test_tipo_desconocido_es_error():
    with pytest.raises(ValueError, match="Novedad de día"):
        _auxilio(dias_sin_auxilio={date(2026, 11, 2): "vacaciones"})
