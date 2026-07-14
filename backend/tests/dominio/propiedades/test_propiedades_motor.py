"""Property-based tests del motor (hypothesis): invariantes que deben cumplirse
para CUALQUIER turno, no solo los casos golden."""

from datetime import date, time, timedelta

from hypothesis import given, settings
from hypothesis import strategies as st

from nomina.dominio.entidades.turno import Turno
from nomina.dominio.servicios.calculadora import _clasificar
from nomina.dominio.servicios.calendario_festivos import CalendarioFestivos
from nomina.dominio.servicios.clasificador_extras import (
    PRESUPUESTO_QUINCENAL,
    SEMANAL_LEGAL,
    clasificar_extras,
)
from nomina.dominio.servicios.segmentador import segmentar, segmentar_turnos
from nomina.semilla import parametros_semilla

PARAMETROS = parametros_semilla()
CALENDARIO = CalendarioFestivos()

fechas = st.dates(min_value=date(2025, 1, 1), max_value=date(2027, 12, 31))
horas = st.integers(min_value=0, max_value=24 * 60 - 1).map(
    lambda m: time(hour=m // 60, minute=m % 60)
)
turnos = st.builds(Turno, fecha=fechas, hora_inicio=horas, hora_fin=horas)


@given(turno=turnos)
def test_suma_de_tramos_igual_duracion_del_turno(turno: Turno):
    tramos = segmentar(turno, PARAMETROS, CALENDARIO)
    assert sum(t.minutos for t in tramos) == turno.minutos


@given(turno=turnos)
def test_tramos_contiguos_y_dentro_del_turno(turno: Turno):
    tramos = segmentar(turno, PARAMETROS, CALENDARIO)
    inicio, fin = turno.intervalo()
    assert tramos[0].inicio == inicio
    assert tramos[-1].fin == fin
    for a, b in zip(tramos, tramos[1:]):
        assert a.fin == b.inicio


@given(turno=turnos)
def test_ningun_tramo_sin_tarifa_definida(turno: Turno):
    """Todo tramo (extra o no) debe clasificar a un concepto con factor, o ser
    hora ordinaria diurna cubierta por el salario (None)."""
    for tramo in segmentar(turno, PARAMETROS, CALENDARIO):
        for variante in (tramo, tramo.como_extra()):
            clasificacion = _clasificar(variante, PARAMETROS)
            if clasificacion is not None:
                assert clasificacion.factor > 0
            else:
                assert not variante.es_extra


@given(turno=turnos)
def test_segmentar_es_idempotente(turno: Turno):
    """Volver a segmentar cada tramo produce ese mismo tramo, entero."""
    for tramo in segmentar(turno, PARAMETROS, CALENDARIO):
        como_turno = Turno(
            fecha=tramo.fecha,
            hora_inicio=tramo.inicio.timetz().replace(tzinfo=None),
            hora_fin=tramo.fin.timetz().replace(tzinfo=None),
        )
        assert segmentar(como_turno, PARAMETROS, CALENDARIO) == [tramo]


@settings(max_examples=50)
@given(
    fecha_base=st.dates(min_value=date(2025, 1, 1), max_value=date(2027, 12, 1)),
    duraciones=st.lists(st.integers(min_value=1, max_value=16), min_size=1, max_size=15),
    estrategia=st.sampled_from([PRESUPUESTO_QUINCENAL, SEMANAL_LEGAL]),
)
def test_clasificar_preserva_los_minutos(fecha_base, duraciones, estrategia):
    """La clasificación parte tramos pero nunca crea ni pierde minutos, y las
    extras de cada día aparecen después de las ordinarias."""
    turnos_periodo = [
        Turno(fecha_base + timedelta(days=i), time(6, 0), time(6 + horas_dia, 0))
        for i, horas_dia in enumerate(duraciones)
    ]
    tramos = segmentar_turnos(turnos_periodo, PARAMETROS, CALENDARIO)
    clasificados = clasificar_extras(tramos, PARAMETROS, fecha_base, estrategia)

    assert sum(t.minutos for t in clasificados) == sum(t.minutos for t in tramos)
    # dentro de la secuencia cronológica de una misma semana/quincena, una vez
    # empieza la hora extra no se vuelve a hora ordinaria (por semana ISO)
    if estrategia == PRESUPUESTO_QUINCENAL:
        vistos_extra = False
        for t in clasificados:
            if t.es_extra:
                vistos_extra = True
            elif vistos_extra:
                raise AssertionError("hora ordinaria después de una extra")
