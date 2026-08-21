from __future__ import annotations

import enum
from dataclasses import dataclass, replace
from datetime import date, datetime, timedelta


class Franja(enum.Enum):
    DIURNA = "diurna"
    NOCTURNA = "nocturna"


class TipoDia(enum.Enum):
    ORDINARIO = "ordinario"
    DOMINICAL = "dominical"
    FESTIVO = "festivo"


@dataclass(frozen=True)
class Tramo:
    """Fragmento homogéneo de un turno: una sola tarifa aplicable.

    Un tramo nunca cruza medianoche ni un límite de jornada nocturna,
    por lo que su fecha, franja y tipo de día son únicos.

    `jornada_ordinaria` indica que el tramo viene de un turno marcado como
    jornada ordinaria y que YA quedó clasificado en la segmentación; el
    clasificador de extras no lo toca. Combinado con `es_extra`:

    | jornada_ordinaria | es_extra | significado          | pago adicional        |
    |-------------------|----------|----------------------|-----------------------|
    | False             | —        | tramo normal         | lo decide la estrategia |
    | True              | False    | dentro del umbral    | ninguno (lo cubre el salario) |
    | True              | True     | excedente del umbral | extra + su tipo de día real |
    """

    inicio: datetime
    fin: datetime
    franja: Franja
    tipo_dia: TipoDia
    es_extra: bool = False
    jornada_ordinaria: bool = False

    def __post_init__(self) -> None:
        if self.fin <= self.inicio:
            raise ValueError(f"Tramo inválido: fin {self.fin} <= inicio {self.inicio}")
        if self.inicio.date() != self.fin.date() and not (
            self.fin.time() == datetime.min.time() and (self.fin.date() - self.inicio.date()).days == 1
        ):
            raise ValueError("Un tramo no puede cruzar medianoche")

    @property
    def fecha(self) -> date:
        """Día calendario al que pertenece el tramo (día en que inicia)."""
        return self.inicio.date()

    @property
    def minutos(self) -> int:
        return int((self.fin - self.inicio).total_seconds() // 60)

    def partir_en(self, minutos: int) -> tuple[Tramo, Tramo]:
        """Divide el tramo tras `minutos` desde su inicio. 0 < minutos < duración."""
        if not 0 < minutos < self.minutos:
            raise ValueError(f"Corte fuera del tramo: {minutos} min de {self.minutos}")
        corte = self.inicio + timedelta(minutes=minutos)
        return replace(self, fin=corte), replace(self, inicio=corte)

    def como_extra(self) -> Tramo:
        return replace(self, es_extra=True)
