"""Turno marcado como «jornada ordinaria».

El turno se registró para cuadrar las horas de la quincena, no porque se
trabajara: sus primeras N horas no pagan recargo dominical/festivo ni nocturno
y solo el excedente sobre N se reconoce, como hora extra.
"""

from datetime import date, time

import pytest

from nomina.dominio.entidades.turno import Turno
from nomina.dominio.servicios.calendario_festivos import CalendarioFestivos
from nomina.dominio.servicios.clasificador_extras import clasificar_extras
from nomina.dominio.servicios.segmentador import segmentar
from nomina.dominio.valores.tramo import Franja, TipoDia
from nomina.semilla import parametros_semilla

PARAMETROS = parametros_semilla()
CALENDARIO = CalendarioFestivos()
DOMINGO = date(2026, 3, 8)


def _segmentar(inicio: str, fin: str, minutos: int | None) -> list:
    turno = Turno(
        DOMINGO, time.fromisoformat(inicio), time.fromisoformat(fin),
        minutos_jornada_ordinaria=minutos,
    )
    return segmentar(turno, PARAMETROS, CALENDARIO)


def test_umbral_dentro_de_un_tramo_lo_parte():
    """Domingo 06:00-16:00 (10 h) con umbral 7 h: 7 h neutras + 3 h extra."""
    tramos = _segmentar("06:00", "16:00", 7 * 60)
    assert [(t.minutos, t.jornada_ordinaria, t.es_extra) for t in tramos] == [
        (7 * 60, True, False),
        (3 * 60, True, True),
    ]
    # el excedente conserva su tipo de día y franja reales
    assert tramos[1].tipo_dia is TipoDia.DOMINICAL
    assert tramos[1].franja is Franja.DIURNA
    # invariante: la suma de los tramos sigue siendo la duración del turno
    assert sum(t.minutos for t in tramos) == 10 * 60


def test_turno_mas_corto_que_el_umbral_queda_todo_neutro():
    tramos = _segmentar("06:00", "13:00", 7 * 60)
    assert [(t.minutos, t.jornada_ordinaria, t.es_extra) for t in tramos] == [
        (7 * 60, True, False)
    ]


def test_umbral_a_traves_de_varios_tramos_nocturnos():
    """Domingo 18:00 → lunes 04:00 con umbral 7 h.

    Segmenta en dom 18-19 diurna, dom 19-24 nocturna y lun 00-04 nocturna; el
    umbral cae a la 01:00, dentro del tercer tramo.
    """
    tramos = _segmentar("18:00", "04:00", 7 * 60)
    assert [(t.minutos, t.jornada_ordinaria, t.es_extra) for t in tramos] == [
        (60, True, False),      # dom 18:00-19:00
        (5 * 60, True, False),  # dom 19:00-00:00
        (60, True, False),      # lun 00:00-01:00
        (3 * 60, True, True),   # lun 01:00-04:00
    ]
    assert sum(t.minutos for t in tramos) == 10 * 60


def test_el_clasificador_de_extras_no_toca_los_tramos_marcados():
    """Ninguna estrategia reclasifica un turno marcado, pero sus minutos sí
    consumen presupuesto ordinario: para eso se registró el turno."""
    tramos = _segmentar("06:00", "16:00", 7 * 60)
    for estrategia in ("presupuesto_quincenal", "semanal_legal", "diaria", "jornada"):
        clasificados = clasificar_extras(tramos, PARAMETROS, date(2026, 3, 1), estrategia)
        assert [(t.minutos, t.es_extra) for t in clasificados] == [
            (7 * 60, False),
            (3 * 60, True),
        ], estrategia


def test_turno_sin_marcar_no_cambia():
    tramos = _segmentar("06:00", "16:00", None)
    assert [(t.minutos, t.jornada_ordinaria, t.es_extra) for t in tramos] == [
        (10 * 60, False, False)
    ]


def test_jornada_ordinaria_debe_ser_positiva():
    with pytest.raises(ValueError):
        Turno(DOMINGO, time(6), time(16), minutos_jornada_ordinaria=0)
