"""Golden test de EDIFICIO RIO CLARO P.H, quincena 16–31 jul 2026.

Es la quincena que estrenó el concepto `dia_31`: julio tiene 31 días pero la
planilla liquida siempre 15 (`DIAS LAB = 15` → 105 h de TIEMPO ORDINARIO), así que
el 31 queda fuera del presupuesto y se reconoce aparte, a hora base.

Reproduce `JULIO RIO CLARO 2026.xlsx` con turnos reconstruidos + estrategia
`jornada` + factores por unidad + descuento de seguridad social. RIGOBERTO cuadra
al peso; WALTER y OLGA quedan a 1 peso por redondeo del documento.

Diferencia documentada:

- FREDY, DIA 31: la planilla liquida $8.344,64 por un error de su fórmula
  (`=+B17*(M2+C17+F17+I17)` multiplica pesos por horas: le suma las 7 horas
  nocturnas del 31 a la tarifa y luego multiplica por 1). La intención —y lo que
  la misma fórmula produce en WALTER, cuyas otras celdas del 31 están vacías— es
  `horas no-extra del 31 × hora base` = 8 × 8.337,64 = $66.701,14. El motor paga
  eso; de ahí los $58.357 de más en su total devengado (y el 4 % correspondiente
  en cada aporte).
- OLGA trabajó 8 h el 31 pero la contadora no le reconoció la línea («los turnos
  de empleada no cumplen con las 105 horas»: sumó 88 h y ya se le pagan 105).
  Se reproduce dejándola sin la marca, que es justo lo que hace el checkbox.
"""

from decimal import Decimal

import pytest

from nomina import rio_claro_16_31 as datos
from nomina.dominio.servicios.calculadora import liquidar
from nomina.dominio.servicios.calendario_festivos import CalendarioFestivos
from nomina.dominio.servicios.clasificador_extras import clasificar_extras
from nomina.dominio.servicios.segmentador import segmentar_turnos
from nomina.semilla import parametros_semilla

PARAMETROS = parametros_semilla()
CALENDARIO = CalendarioFestivos()

FREDY, RIGOBERTO, WALTER, OLGA = "15536952", "71392880", "71878165", "43581748"


def _liquidar(documento: str):
    tramos = segmentar_turnos(datos.turnos_de(documento), PARAMETROS, CALENDARIO)
    clasificados = clasificar_extras(
        tramos, PARAMETROS, datos.PERIODO_INICIO, estrategia=datos.ESTRATEGIA_EXTRAS
    )
    return liquidar(
        clasificados,
        datos.SALARIO_BASICO,
        PARAMETROS,
        datos.PERIODO_INICIO,
        factores_override=datos.FACTORES_OVERRIDE,
        conceptos_manuales=datos.CONCEPTOS_MANUALES.get(documento, ()),
        descontar_seguridad_social=True,
        pagar_dia_31=documento in datos.PAGA_DIA_31,
    )


def _horas(liq) -> dict[str, float]:
    return {c.codigo: float(c.horas) for c in liq.conceptos if c.minutos}


def _por_codigo(liq) -> dict[str, int]:
    valores = {c.codigo: int(c.valor) for c in liq.conceptos}
    return valores | {d.codigo: int(d.valor) for d in liq.deducciones}


def test_fredy():
    """Nocturno el 16 y el 31; el del 31 cruza a agosto y entra completo."""
    liq = _liquidar(FREDY)
    assert _horas(liq) == {
        "tiempo_ordinario": 105.0, "recargo_nocturno": 21.5, "festivo_diurno": 20.0,
        "festivo_nocturno": 2.5, "extra_diurna": 4.0, "extra_nocturna": 6.0, "dia_31": 8.0,
    }
    v = _por_codigo(liq)
    assert v["tiempo_ordinario"] == 875_453  # 105 h × 8.337,642857…
    assert v["festivo_diurno"] == 316_830
    assert v["extra_diurna"] == 41_688
    assert v["recargo_nocturno"] == 62_741
    assert v["extra_nocturna"] == 87_545
    assert v["festivo_nocturno"] == 43_773
    assert v["auxilio_transporte"] == 124_548
    # La planilla dice 8.344,64 por el bug de su fórmula; ver el docstring.
    assert v["dia_31"] == 66_701


def test_rigoberto_no_trabajo_el_31():
    """Cuadra al peso con la planilla: no hay línea de día 31 que discrepe."""
    liq = _liquidar(RIGOBERTO)
    assert "dia_31" not in _horas(liq)
    v = _por_codigo(liq)
    assert v == {
        "tiempo_ordinario": 875_453, "recargo_nocturno": 141_531, "festivo_diurno": 158_415,
        "festivo_nocturno": 218_863, "extra_diurna": 125_065, "extra_nocturna": 131_318,
        "auxilio_transporte": 124_548, "otro_devengado": 19_403,
        "aporte_salud": 66_802, "aporte_pension": 66_802, "otra_deduccion": 50_000,
    }
    assert liq.total_devengado == Decimal(1_794_596)
    assert liq.neto_a_pagar == Decimal(1_610_992)


def test_walter_turno_de_dia_el_31():
    """El caso que la fórmula de la planilla acierta: 8 h × hora base = $66.701,14."""
    liq = _liquidar(WALTER)
    assert _horas(liq)["dia_31"] == 8.0
    v = _por_codigo(liq)
    assert v["dia_31"] == 66_701
    assert v["festivo_nocturno"] == 262_636
    assert v["recargo_nocturno"] == 119_645
    # La planilla: TOTAL DEVENGADO 1.688.689,30 / VALOR A PAGAR 1.490.337,96.
    assert liq.total_devengado == Decimal(1_688_690)
    assert liq.neto_a_pagar == Decimal(1_490_338)


def test_olga_sin_la_marca_no_recibe_el_dia_31():
    """88 h en la quincena: la contadora no le reconoció el 31 y sin marca tampoco el motor."""
    liq = _liquidar(OLGA)
    assert "dia_31" not in _horas(liq)
    assert _horas(liq) == {"tiempo_ordinario": 105.0}
    assert liq.total_devengado == Decimal(1_000_001)  # planilla: 1.000.000


@pytest.mark.parametrize("documento", [FREDY, WALTER])
def test_el_dia_31_no_toca_el_auxilio_de_transporte(documento):
    """El auxilio sigue siendo el quincenal plano: el 31 no agrega auxilio."""
    assert _por_codigo(_liquidar(documento))["auxilio_transporte"] == 124_548
