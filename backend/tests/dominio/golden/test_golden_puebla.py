"""Golden test de la unidad EDIFICIO PUEBLA P.H (quincena 1–15 jul 2026).

Reproduce la planilla real de la contadora (`NOMINA PUEBLA JULIO.xlsx`) con el motor:
turnos reconstruidos + estrategia `diaria` + factores por unidad + descuento de
seguridad social. Los valores esperados son los del documento (redondeados a peso),
salvo dos diferencias DOCUMENTADAS.

NOTA: la unidad Puebla en vivo usa hoy la estrategia `jornada` (extras por turno
continuo, decisión del usuario). Este test fija `diaria` a propósito para conservar
la reproducción del documento como referencia verificada; el comportamiento `jornada`
se prueba en `tests/dominio/test_clasificador_jornada.py`.

Diferencias documentadas:

- Maria, NOCTURNO DOMINICAL: el documento cuenta 9 h (2 de ellas de un turno de
  domingo que cruza a lunes); el motor corta el dominical a medianoche (regla de
  negocio de este repo) → 7 h. Todos los demás conceptos coinciden al peso.
- Wilmar, SALUD/PENSIÓN: la planilla incluyó la cuota de manejo ($7.095) en su IBC;
  la regla correcta la excluye → ~$284 menos por aporte.
"""

from decimal import Decimal

from nomina import puebla
from nomina.dominio.servicios.calculadora import liquidar
from nomina.dominio.servicios.calendario_festivos import CalendarioFestivos
from nomina.dominio.servicios.clasificador_extras import clasificar_extras
from nomina.dominio.servicios.segmentador import segmentar_turnos
from nomina.semilla import parametros_semilla

PARAMETROS = parametros_semilla()
CALENDARIO = CalendarioFestivos()


def _liquidar(documento: str):
    tramos = segmentar_turnos(puebla.turnos_de(documento), PARAMETROS, CALENDARIO)
    clasificados = clasificar_extras(
        tramos, PARAMETROS, puebla.PERIODO_INICIO, estrategia="diaria"
    )
    return liquidar(
        clasificados,
        puebla.SALARIO_BASICO,
        PARAMETROS,
        puebla.PERIODO_INICIO,
        factores_override=puebla.FACTORES_OVERRIDE,
        conceptos_manuales=(puebla.CUOTA_MANEJO,),
        descontar_seguridad_social=True,
    )


def _por_codigo(liq) -> dict[str, int]:
    valores = {c.codigo: int(c.valor) for c in liq.conceptos}
    valores |= {d.codigo: int(d.valor) for d in liq.deducciones}
    return valores


def _horas(liq) -> dict[str, int]:
    return {c.codigo: int(c.horas.to_integral_value()) for c in liq.conceptos if c.minutos}


def test_wilmar_coincide_al_peso_en_devengados():
    """Wilmar: todos los devengados coinciden al peso con el documento."""
    liq = _liquidar("71726091")
    v = _por_codigo(liq)
    assert _horas(liq) == {
        "tiempo_ordinario": 110, "recargo_nocturno": 51, "festivo_diurno": 9,
        "festivo_nocturno": 7, "extra_diurna": 4, "extra_nocturna": 12,
        "extra_nocturna_festiva": 4,
    }
    # Valores del documento (redondeados a peso).
    assert v["tiempo_ordinario"] == 875_453
    assert v["recargo_nocturno"] == 142_062
    assert v["festivo_diurno"] == 136_093
    assert v["festivo_nocturno"] == 116_992
    assert v["extra_diurna"] == 39_793
    assert v["extra_nocturna"] == 167_132
    assert v["extra_nocturna_festiva"] == 79_587
    assert v["auxilio_transporte"] == 124_548
    assert v["otro_devengado"] == 7_095  # cuota de manejo
    assert int(liq.total_devengado) == 1_688_755  # documento: 1.688.754,15
    # Deducciones: regla correcta (IBC sin cuota). Documento (con cuota): 62.568 c/u.
    assert v["aporte_salud"] == 62_284
    assert v["aporte_pension"] == 62_284
    assert int(liq.neto_a_pagar) == 1_564_187


def test_maria_coincide_salvo_dominical_que_cruza_medianoche():
    """Maria: todo coincide al peso salvo el nocturno dominical (regla de medianoche)."""
    liq = _liquidar("43623487")
    v = _por_codigo(liq)
    assert _horas(liq) == {
        "tiempo_ordinario": 110, "recargo_nocturno": 30, "festivo_diurno": 9,
        "festivo_nocturno": 7, "extra_diurna": 8, "extra_nocturna": 4,
        "extra_diurna_festiva": 4, "extra_nocturna_festiva": 4,
    }
    assert v["tiempo_ordinario"] == 875_453
    assert v["recargo_nocturno"] == 83_566        # documento: 83.565,92
    assert v["festivo_diurno"] == 136_093          # documento: 136.093,07
    assert v["extra_diurna"] == 79_587             # documento: 79.586,59
    assert v["extra_nocturna"] == 55_711           # documento: 55.710,61
    assert v["extra_diurna_festiva"] == 63_669     # documento: 63.669,27
    assert v["extra_nocturna_festiva"] == 79_587   # documento: 79.586,59
    assert v["otro_devengado"] == 7_095
    # Diferencia documentada: el documento paga 9 h (150.419); el motor 7 h.
    assert v["festivo_nocturno"] == 116_992
    assert int(liq.total_devengado) == 1_622_301


def test_puebla_descuenta_solo_si_la_unidad_lo_pide():
    """Sin descontar_seguridad_social no hay deducciones automáticas."""
    tramos = segmentar_turnos(puebla.turnos_de("43623487"), PARAMETROS, CALENDARIO)
    clasificados = clasificar_extras(
        tramos, PARAMETROS, puebla.PERIODO_INICIO, estrategia="diaria"
    )
    liq = liquidar(
        clasificados, puebla.SALARIO_BASICO, PARAMETROS, puebla.PERIODO_INICIO,
        factores_override=puebla.FACTORES_OVERRIDE,
        conceptos_manuales=(puebla.CUOTA_MANEJO,),
        descontar_seguridad_social=False,
    )
    assert liq.deducciones == ()
    assert liq.total_deducciones == Decimal(0)
    assert liq.neto_a_pagar == liq.total_devengado
