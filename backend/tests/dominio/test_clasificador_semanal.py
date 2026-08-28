"""Estrategia `semanal_legal`: el presupuesto es la semana calendario (lunes a
domingo), no el periodo liquidado.

El caso que motiva `tramos_contexto`: una semana partida por el corte de quincena.
Sin contexto cada liquidación arranca el contador en cero y la misma semana recibe
42 h de presupuesto dos veces, así que las horas del otro lado del corte salen
gratis. Datos reales de MARIA HERESBEY AGUIRRE (Puebla, agosto 2026): la semana
lunes 10 – domingo 16 tiene 44 h en la quincena 1–15 y 12 h en la 16–31.
"""

from datetime import date, time

from nomina.dominio.entidades.turno import Turno
from nomina.dominio.servicios.calendario_festivos import CalendarioFestivos
from nomina.dominio.servicios.clasificador_extras import clasificar_extras
from nomina.dominio.servicios.segmentador import segmentar_turnos
from nomina.semilla import parametros_semilla

PARAMETROS = parametros_semilla()
CALENDARIO = CalendarioFestivos()

# Semana ISO lunes 10 – domingo 16 de agosto de 2026, jornada máxima 42 h.
PRIMERA_QUINCENA = [
    Turno(date(2026, 8, d), time(6), time(14)) for d in (10, 11, 12, 13)
] + [Turno(date(2026, 8, 15), time(6), time(18))]  # 4×8 + 12 = 44 h
SEGUNDA_QUINCENA = [Turno(date(2026, 8, 16), time(6), time(18))]  # 12 h


def _tramos(turnos):
    return segmentar_turnos(turnos, PARAMETROS, CALENDARIO)


def _clasificar(turnos, fecha_periodo, contexto=()):
    return clasificar_extras(
        _tramos(turnos),
        PARAMETROS,
        fecha_periodo,
        estrategia="semanal_legal",
        tramos_contexto=contexto,
    )


def _horas_extra(tramos):
    return sum(t.minutos for t in tramos if t.es_extra) / 60


def test_la_primera_quincena_cobra_lo_que_pasa_de_42_horas():
    # 44 h dentro del periodo → 2 h extra.
    assert _horas_extra(_clasificar(PRIMERA_QUINCENA, date(2026, 8, 1))) == 2


def test_sin_contexto_la_semana_partida_recibe_presupuesto_dos_veces():
    # Las 12 h del domingo caen en la quincena siguiente, que reinicia el contador
    # en cero: 12 < 42 → no reconoce extra. Este es el error que `tramos_contexto` tapa.
    assert _horas_extra(_clasificar(SEGUNDA_QUINCENA, date(2026, 8, 16))) == 0


def test_con_contexto_la_semana_se_cuenta_completa():
    # Las 44 h de la quincena anterior ya agotaron el presupuesto de esa semana,
    # así que las 12 h del domingo son todas extra. 2 + 12 = 14 h en la semana de 56 h.
    contexto = _tramos(PRIMERA_QUINCENA)
    assert _horas_extra(_clasificar(SEGUNDA_QUINCENA, date(2026, 8, 16), contexto)) == 12


def test_el_contexto_no_se_liquida():
    contexto = _tramos(PRIMERA_QUINCENA)
    tramos = _clasificar(SEGUNDA_QUINCENA, date(2026, 8, 16), contexto)
    # Solo salen los tramos del periodo: nada anterior al 16 se vuelve a pagar.
    assert {t.fecha for t in tramos} == {date(2026, 8, 16)}
    assert sum(t.minutos for t in tramos) == 12 * 60


def test_el_contexto_de_otra_semana_no_gasta_presupuesto():
    # Un turno del lunes 3 (semana anterior) no puede consumir el cupo de la semana
    # del 10 al 16: los acumulados van por (año ISO, semana ISO).
    contexto = _tramos([Turno(date(2026, 8, 3), time(6), time(18))])
    assert _horas_extra(_clasificar(SEGUNDA_QUINCENA, date(2026, 8, 16), contexto)) == 0


def test_las_otras_estrategias_ignoran_el_contexto():
    contexto = _tramos(PRIMERA_QUINCENA)
    for estrategia in ("jornada", "diaria", "presupuesto_quincenal"):
        tramos = clasificar_extras(
            _tramos(SEGUNDA_QUINCENA),
            PARAMETROS,
            date(2026, 8, 16),
            estrategia=estrategia,
            tramos_contexto=contexto,
        )
        # Turno de 12 h: 8 ordinarias + 4 extra con umbral por turno/día; el
        # presupuesto quincenal (105 h) no se toca con 12 h.
        esperado = 4 if estrategia in ("jornada", "diaria") else 0
        assert _horas_extra(tramos) == esperado, estrategia
