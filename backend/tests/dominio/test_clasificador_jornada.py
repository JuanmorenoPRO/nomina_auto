"""Estrategia de extras `jornada`: el umbral de 8 h se cuenta por TURNO continuo,
no por día calendario. Las horas de sobre-jornada caen al final del turno con el
recargo del día/franja donde caen (la madrugada de un domingo es dominical)."""

from datetime import date, time
from decimal import Decimal

from nomina.dominio.entidades.turno import Turno
from nomina.dominio.servicios.calculadora import liquidar
from nomina.dominio.servicios.calendario_festivos import CalendarioFestivos
from nomina.dominio.servicios.clasificador_extras import clasificar_extras
from nomina.dominio.servicios.segmentador import segmentar_turnos
from nomina.dominio.valores.tramo import Franja, TipoDia
from nomina.semilla import parametros_semilla

PARAMETROS = parametros_semilla()
CALENDARIO = CalendarioFestivos()


def _clasificar(turnos, estrategia):
    tramos = segmentar_turnos(turnos, PARAMETROS, CALENDARIO)
    return clasificar_extras(tramos, PARAMETROS, date(2026, 7, 1), estrategia=estrategia)


def _min_extra(tramos):
    return sum(t.minutos for t in tramos if t.es_extra)


def test_turno_cruza_medianoche_extra_cae_en_madrugada_dominical():
    # Sábado 11-jul 18:00 → domingo 12-jul 06:00 (12 h continuas).
    turnos = [Turno(date(2026, 7, 11), time(18), time(6))]
    tramos = _clasificar(turnos, "jornada")

    extras = [t for t in tramos if t.es_extra]
    assert _min_extra(tramos) == 4 * 60  # 4 h de sobre-jornada
    # las 4 h extra caen ya en el domingo, de noche → dominical + nocturna
    assert all(t.fecha == date(2026, 7, 12) for t in extras)
    assert all(t.tipo_dia is TipoDia.DOMINICAL and t.franja is Franja.NOCTURNA for t in extras)

    # Y al liquidar quedan como concepto de extra nocturna festiva (no la plana).
    liq = liquidar(tramos, Decimal("1750905"), PARAMETROS, date(2026, 7, 1),
                   incluir_auxilio_transporte=False)
    codigos = {c.codigo: c for c in liq.conceptos if c.minutos}
    assert "extra_nocturna_festiva" in codigos
    assert int(codigos["extra_nocturna_festiva"].horas.to_integral_value()) == 4
    assert "extra_nocturna" not in codigos  # no hay extra nocturna ordinaria


def test_turnos_partidos_con_hueco_no_generan_extra_pero_diaria_si():
    # Mismo día, dos turnos de 5 h separados por un descanso: 10 h en el día.
    turnos = [
        Turno(date(2026, 7, 6), time(6), time(11)),   # 5 h
        Turno(date(2026, 7, 6), time(14), time(19)),  # 5 h
    ]
    # jornada: dos jornadas de 5 h (<8) → sin extra.
    assert _min_extra(_clasificar(turnos, "jornada")) == 0
    # diaria: 10 h en el día → 2 h extra. Contraste explícito de la diferencia.
    assert _min_extra(_clasificar(turnos, "diaria")) == 2 * 60


def test_cada_jornada_resetea_su_umbral_independiente():
    # Dos turnos nocturnos de 8 h en días distintos; cada uno es su propia jornada.
    turnos = [
        Turno(date(2026, 7, 8), time(22), time(6)),   # mié 22:00 → jue 06:00
        Turno(date(2026, 7, 9), time(22), time(6)),   # jue 22:00 → vie 06:00
    ]
    # Ninguna jornada supera 8 h → sin extra, aunque el jueves reciba la cola del miércoles.
    assert _min_extra(_clasificar(turnos, "jornada")) == 0
