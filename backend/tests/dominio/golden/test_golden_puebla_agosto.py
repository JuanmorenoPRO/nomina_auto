"""Golden de EDIFICIO PUEBLA P.H, agosto 2026, con los turnos REALES de producción.

Fija dos escenarios sobre los mismos datos:

- **`jornada` + factores de la unidad** — lo que producción liquidó (v7 de la
  quincena 1–15 y v5 de la 16–31). Queda anclado para que se vea qué cambia.
- **`semanal_legal` + factores aditivos** — el criterio legal: trabajo
  suplementario es el que excede la jornada ordinaria, 8 h/día y 42 h/semana
  desde el 15-jul-2026 (CST art. 159 y 161, Ley 2101/2021), y el recargo
  dominical vigente es el 90 % (Ley 2466/2025), no el 75 % de la tabla legada.

Hasta ahora ningún golden cubría el camino que producción usaba de verdad:
`test_golden_puebla.py` fija `diaria` sobre turnos reconstruidos de julio.

La discusión con la contadora, que este golden zanja: ella cargó 14 h de extra
nocturna en los turnos del 24 al 27 de agosto, que son de 22:00 a 06:00 —8 h
exactas—; ver `test_un_turno_de_ocho_horas_nunca_genera_extra`.
"""

from decimal import Decimal

import pytest

from nomina import puebla_agosto as datos
from nomina.dominio.servicios.calculadora import liquidar
from nomina.dominio.servicios.calendario_festivos import CalendarioFestivos
from nomina.dominio.servicios.clasificador_extras import clasificar_extras
from nomina.dominio.servicios.segmentador import segmentar_turnos
from nomina.semilla import parametros_semilla

PARAMETROS = parametros_semilla()
CALENDARIO = CalendarioFestivos()

MARIA, WILMAR = datos.MARIA, datos.WILMAR
PRIMERA, SEGUNDA = datos.PRIMERA_QUINCENA, datos.SEGUNDA_QUINCENA


def _liquidar(documento, quincena, *, estrategia, factores_override, con_semana_previa):
    tramos = segmentar_turnos(datos.turnos_de(documento, quincena), PARAMETROS, CALENDARIO)
    contexto = (
        segmentar_turnos(
            datos.turnos_semana_previa(documento, quincena), PARAMETROS, CALENDARIO
        )
        if con_semana_previa
        else ()
    )
    clasificados = clasificar_extras(
        tramos, PARAMETROS, quincena[0], estrategia=estrategia, tramos_contexto=contexto
    )
    return liquidar(
        clasificados,
        datos.SALARIO_BASICO,
        PARAMETROS,
        quincena[0],
        factores_override=factores_override,
        conceptos_manuales=(datos.CUOTA_MANEJO,),
        descontar_seguridad_social=True,
        pagar_dia_31=(quincena == SEGUNDA and documento in datos.PAGA_DIA_31),
    )


def _como_estaba(documento, quincena):
    """Config anterior: umbral por turno + tabla de factores legada."""
    return _liquidar(
        documento, quincena,
        estrategia="jornada",
        factores_override=datos.FACTORES_OVERRIDE,
        con_semana_previa=False,
    )


def _criterio_legal(documento, quincena):
    """Config vigente: jornada máxima semanal + factores aditivos."""
    return _liquidar(
        documento, quincena,
        estrategia="semanal_legal",
        factores_override=None,
        con_semana_previa=True,
    )


def _horas(liq) -> dict[str, float]:
    return {c.codigo: float(c.horas) for c in liq.conceptos if c.minutos}


def _valores(liq) -> dict[str, int]:
    return {c.codigo: int(c.valor) for c in liq.conceptos} | {
        d.codigo: int(d.valor) for d in liq.deducciones
    }


# --- Lo que producción liquidó (ancla del "antes") ---------------------------


def test_maria_16_31_reproduce_la_v5_de_produccion():
    liq = _como_estaba(MARIA, SEGUNDA)
    assert _horas(liq) == {
        "tiempo_ordinario": 105.0, "recargo_nocturno": 55.0, "festivo_diurno": 14.0,
        "festivo_nocturno": 10.0, "extra_diurna": 4.0, "extra_nocturna": 8.0,
        "extra_diurna_festiva": 4.0, "extra_nocturna_festiva": 4.0, "dia_31": 8.0,
    }
    assert _valores(liq) == {
        "tiempo_ordinario": 875_453, "recargo_nocturno": 160_500, "festivo_diurno": 221_781,
        "festivo_nocturno": 175_091, "extra_diurna": 41_688, "extra_nocturna": 116_727,
        "extra_diurna_festiva": 66_701, "extra_nocturna_festiva": 83_376, "dia_31": 66_701,
        "auxilio_transporte": 124_548, "otro_devengado": 7_095,
        "aporte_salud": 72_321, "aporte_pension": 72_321,
    }
    assert liq.neto_a_pagar == Decimal(1_795_019)


def test_maria_1_15_reproduce_la_v7_de_produccion():
    liq = _como_estaba(MARIA, PRIMERA)
    assert liq.total_devengado == Decimal(1_697_869)
    assert liq.neto_a_pagar == Decimal(1_572_571)


def test_wilmar_1_15_reproduce_produccion():
    """La marca de jornada ordinaria del 7-ago (06:00→13:00, 7 h) se conserva: ese
    turno es relleno para cuadrar la quincena, no trabajo real. Su fila en la planilla
    cuadra exacto (119 h registradas = 119 h del documento)."""
    assert _como_estaba(WILMAR, PRIMERA).neto_a_pagar == Decimal(1_346_286)


def test_wilmar_16_31_con_el_turno_del_17_corregido():
    """Producción v5 dio $1.699.519 con la marca de jornada ordinaria mal puesta en el
    turno del 17-ago (22:00→06:00): le suprimía los recargos de un turno que la
    contadora sí liquidó con ellos. Sin la marca, ese turno paga nocturno 6 h +
    nocturno festivo 2 h, que es exactamente lo que ella pagó."""
    liq = _como_estaba(WILMAR, SEGUNDA)
    assert _valores(liq)["dia_31"] == 66_701
    assert liq.neto_a_pagar == Decimal(1_734_423)


# --- El criterio legal (lo que se adopta) ------------------------------------


def test_maria_16_31_con_el_criterio_legal():
    """132 h trabajadas en semanas de 56 / 50 / 62 / 8 h.

    La primera queda partida por el corte de quincena: 44 h se liquidaron en la
    1–15 y 12 h caen aquí, con el presupuesto de esa semana ya gastado — por eso
    esas 12 h son extra completas y por eso hace falta `tramos_contexto`.

    Con el tope de 42 h/semana salen 40 h de trabajo suplementario, contra las
    20 h del umbral por turno. La contadora liquidó 34 h, pero cuadrando a 105 h
    y con 7 h de una fila de festivo dentro del presupuesto.
    """
    liq = _criterio_legal(MARIA, SEGUNDA)
    assert _horas(liq) == {
        "tiempo_ordinario": 105.0, "recargo_nocturno": 50.0, "festivo_diurno": 5.0,
        "festivo_nocturno": 3.0, "extra_diurna": 3.0, "extra_nocturna": 13.0,
        "extra_diurna_festiva": 13.0, "extra_nocturna_festiva": 11.0, "dia_31": 8.0,
    }
    assert liq.total_devengado == Decimal(2_052_219)
    assert liq.neto_a_pagar == Decimal(1_898_573)


def test_los_factores_combinados_usan_el_recargo_dominical_vigente():
    """2.15 / 2.25 / 2.65 = 1 + recargo(0.90) + el que aplique.

    La tabla legada (2.0 / 2.1 / 2.5) los armó con el recargo del 75 %, derogado
    desde el 1-jul-2025. El override pagaba de menos.
    """
    factores = {c.codigo: c.factor for c in _criterio_legal(MARIA, SEGUNDA).conceptos}
    assert factores["festivo_diurno"] == Decimal("1.90")
    assert factores["festivo_nocturno"] == Decimal("2.25")
    assert factores["extra_diurna_festiva"] == Decimal("2.15")
    assert factores["extra_nocturna_festiva"] == Decimal("2.65")


def test_wilmar_16_31_con_el_criterio_legal():
    liq = _criterio_legal(WILMAR, SEGUNDA)
    assert _horas(liq)["dia_31"] == 8.0
    assert liq.neto_a_pagar == Decimal(1_874_411)


@pytest.mark.parametrize(
    ("documento", "quincena", "neto"),
    [
        (MARIA, PRIMERA, 1_650_045),
        (MARIA, SEGUNDA, 1_898_573),
        (WILMAR, PRIMERA, 1_471_319),
        (WILMAR, SEGUNDA, 1_874_411),
    ],
)
def test_el_criterio_legal_paga_mas_que_el_umbral_por_turno(documento, quincena, neto):
    """En las cuatro liquidaciones de agosto el criterio legal sube el neto: el
    tope semanal reconoce más horas suplementarias y los factores son los vigentes."""
    liq = _criterio_legal(documento, quincena)
    assert liq.neto_a_pagar == Decimal(neto)
    assert liq.neto_a_pagar > _como_estaba(documento, quincena).neto_a_pagar


# --- El punto exacto del reclamo a la contadora ------------------------------


def test_un_turno_de_ocho_horas_nunca_genera_extra():
    """Los turnos del 24 al 27 de agosto son 22:00→06:00 = 8 h exactas.

    Ningún umbral —por turno, por día ni por semana— los convierte en trabajo
    suplementario por sí solos. La contadora les cargó 4 + 4 + 4 + 2 = 14 h de
    extra nocturna; el motor no lo hace bajo `jornada` ni bajo `diaria`.
    """
    turnos = [
        t for t in datos.turnos_de(MARIA, SEGUNDA)
        if t.fecha.day in (24, 25, 26, 27)
    ]
    assert len(turnos) == 4
    tramos = segmentar_turnos(turnos, PARAMETROS, CALENDARIO)
    assert sum(t.minutos for t in tramos) == 4 * 8 * 60

    for estrategia in ("jornada", "diaria"):
        clasificados = clasificar_extras(
            tramos, PARAMETROS, SEGUNDA[0], estrategia=estrategia
        )
        assert not any(t.es_extra for t in clasificados), estrategia
