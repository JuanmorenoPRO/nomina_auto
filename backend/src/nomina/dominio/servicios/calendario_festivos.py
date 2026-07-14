"""Calendario de festivos colombianos.

Festivos fijos, festivos móviles derivados de Pascua (algoritmo de Butcher) y
traslado a lunes según la Ley Emiliani (51 de 1983). Admite festivos manuales
que se suman o corrigen a los calculados, por si la ley cambia.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, timedelta

from nomina.dominio.valores.tramo import TipoDia

# Festivos de fecha fija que NO se trasladan (mes, día)
_FIJOS = [(1, 1), (5, 1), (7, 20), (8, 7), (12, 8), (12, 25)]

# Festivos de fecha fija que se trasladan al lunes siguiente (Ley Emiliani)
_EMILIANI = [(1, 6), (3, 19), (6, 29), (8, 15), (10, 12), (11, 1), (11, 11)]

# Festivos móviles: días desde el Domingo de Pascua (negativo = antes)
_PASCUA_SIN_TRASLADO = [-3, -2]  # Jueves y Viernes Santo
_PASCUA_CON_TRASLADO = [39, 60, 68]  # Ascensión, Corpus Christi, Sagrado Corazón


def domingo_de_pascua(anio: int) -> date:
    """Algoritmo de Butcher."""
    a = anio % 19
    b, c = divmod(anio, 100)
    d, e = divmod(b, 4)
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i, k = divmod(c, 4)
    m = (32 + 2 * e + 2 * i - h - k) % 7
    n = (a + 11 * h + 22 * m) // 451
    mes, dia = divmod(h + m - 7 * n + 114, 31)
    return date(anio, mes, dia + 1)


def _al_lunes_siguiente(fecha: date) -> date:
    """Ley Emiliani: si no cae lunes, se traslada al lunes siguiente."""
    return fecha + timedelta(days=(7 - fecha.weekday()) % 7)


def festivos_por_ley(anio: int) -> frozenset[date]:
    pascua = domingo_de_pascua(anio)
    festivos = {date(anio, mes, dia) for mes, dia in _FIJOS}
    festivos |= {_al_lunes_siguiente(date(anio, mes, dia)) for mes, dia in _EMILIANI}
    festivos |= {pascua + timedelta(days=d) for d in _PASCUA_SIN_TRASLADO}
    festivos |= {_al_lunes_siguiente(pascua + timedelta(days=d)) for d in _PASCUA_CON_TRASLADO}
    return frozenset(festivos)


@dataclass(frozen=True)
class CalendarioFestivos:
    """Festivos por ley + ajustes manuales (agregar o quitar fechas)."""

    festivos_manuales: frozenset[date] = field(default_factory=frozenset)
    no_festivos: frozenset[date] = field(default_factory=frozenset)

    def es_festivo(self, fecha: date) -> bool:
        if fecha in self.no_festivos:
            return False
        return fecha in self.festivos_manuales or fecha in festivos_por_ley(fecha.year)

    def tipo_dia(self, fecha: date) -> TipoDia:
        """Tipo de día calendario. Festivo tiene precedencia sobre dominical."""
        if self.es_festivo(fecha):
            return TipoDia.FESTIVO
        if fecha.weekday() == 6:
            return TipoDia.DOMINICAL
        return TipoDia.ORDINARIO
