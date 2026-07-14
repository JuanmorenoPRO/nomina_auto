"""Calendario contra los festivos oficiales de Colombia 2025, 2026 y 2027."""

from datetime import date

from nomina.dominio.servicios.calendario_festivos import (
    CalendarioFestivos,
    domingo_de_pascua,
    festivos_por_ley,
)
from nomina.dominio.valores.tramo import TipoDia

FESTIVOS_2025 = {
    date(2025, 1, 1), date(2025, 1, 6), date(2025, 3, 24), date(2025, 4, 17),
    date(2025, 4, 18), date(2025, 5, 1), date(2025, 6, 2), date(2025, 6, 23),
    date(2025, 6, 30), date(2025, 7, 20), date(2025, 8, 7), date(2025, 8, 18),
    date(2025, 10, 13), date(2025, 11, 3), date(2025, 11, 17), date(2025, 12, 8),
    date(2025, 12, 25),
}

FESTIVOS_2026 = {
    date(2026, 1, 1), date(2026, 1, 12), date(2026, 3, 23), date(2026, 4, 2),
    date(2026, 4, 3), date(2026, 5, 1), date(2026, 5, 18), date(2026, 6, 8),
    date(2026, 6, 15), date(2026, 6, 29), date(2026, 7, 20), date(2026, 8, 7),
    date(2026, 8, 17), date(2026, 10, 12), date(2026, 11, 2), date(2026, 11, 16),
    date(2026, 12, 8), date(2026, 12, 25),
}

FESTIVOS_2027 = {
    date(2027, 1, 1), date(2027, 1, 11), date(2027, 3, 22), date(2027, 3, 25),
    date(2027, 3, 26), date(2027, 5, 1), date(2027, 5, 10), date(2027, 5, 31),
    date(2027, 6, 7), date(2027, 7, 5), date(2027, 7, 20), date(2027, 8, 7),
    date(2027, 8, 16), date(2027, 10, 18), date(2027, 11, 1), date(2027, 11, 15),
    date(2027, 12, 8), date(2027, 12, 25),
}


def test_pascua():
    assert domingo_de_pascua(2025) == date(2025, 4, 20)
    assert domingo_de_pascua(2026) == date(2026, 4, 5)
    assert domingo_de_pascua(2027) == date(2027, 3, 28)


def test_festivos_2025():
    assert festivos_por_ley(2025) == FESTIVOS_2025


def test_festivos_2026():
    assert festivos_por_ley(2026) == FESTIVOS_2026


def test_festivos_2027():
    assert festivos_por_ley(2027) == FESTIVOS_2027


def test_traslado_emiliani():
    # Reyes 2026 (6-ene, martes) se traslada al lunes 12-ene
    assert date(2026, 1, 6) not in festivos_por_ley(2026)
    assert date(2026, 1, 12) in festivos_por_ley(2026)
    # Reyes 2025 (6-ene, lunes) NO se traslada
    assert date(2025, 1, 6) in festivos_por_ley(2025)


def test_tipo_dia():
    cal = CalendarioFestivos()
    assert cal.tipo_dia(date(2026, 3, 2)) is TipoDia.ORDINARIO  # lunes común
    assert cal.tipo_dia(date(2026, 3, 8)) is TipoDia.DOMINICAL
    assert cal.tipo_dia(date(2026, 6, 29)) is TipoDia.FESTIVO  # San Pedro, lunes
    # festivo tiene precedencia sobre dominical
    assert cal.tipo_dia(date(2025, 7, 20)) is TipoDia.FESTIVO  # 20-jul-2025 fue domingo


def test_festivos_manuales():
    cal = CalendarioFestivos(
        festivos_manuales=frozenset({date(2026, 3, 2)}),
        no_festivos=frozenset({date(2026, 6, 29)}),
    )
    assert cal.es_festivo(date(2026, 3, 2))
    assert not cal.es_festivo(date(2026, 6, 29))
