from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from uuid import UUID

from nomina.dominio.valores.tiempo import BOGOTA


@dataclass(frozen=True)
class Turno:
    """Intervalo trabajado por un empleado.

    `fecha` es el día en que el turno INICIA. Si `hora_fin <= hora_inicio`,
    el turno cruza medianoche y termina el día siguiente (hora_fin == hora_inicio
    equivale a 24 horas exactas). Un día con varios turnos es un turno partido;
    un día sin turnos es descanso.

    `minutos_jornada_ordinaria` marca el turno como «jornada ordinaria»: el
    empleado no trabajó realmente ese domingo/festivo, el turno se registró para
    cuadrar las horas de la quincena. Sus primeros N minutos son horas ordinarias
    puras (cubiertas por el salario base: ni recargo dominical/festivo ni
    nocturno) y solo el excedente sobre N se reconoce, como hora extra con su
    tipo de día y franja reales. `None` = turno normal.
    """

    fecha: date
    hora_inicio: time
    hora_fin: time
    minutos_jornada_ordinaria: int | None = None

    def __post_init__(self) -> None:
        if self.minutos_jornada_ordinaria is not None and self.minutos_jornada_ordinaria <= 0:
            raise ValueError(
                f"La jornada ordinaria debe ser positiva: {self.minutos_jornada_ordinaria}"
            )

    def intervalo(self) -> tuple[datetime, datetime]:
        inicio = datetime.combine(self.fecha, self.hora_inicio, tzinfo=BOGOTA)
        fin = datetime.combine(self.fecha, self.hora_fin, tzinfo=BOGOTA)
        if fin <= inicio:
            fin += timedelta(days=1)
        return inicio, fin

    @property
    def minutos(self) -> int:
        inicio, fin = self.intervalo()
        return int((fin - inicio).total_seconds() // 60)


@dataclass(frozen=True)
class TurnoRegistrado:
    """Turno persistido: identidad + empleado + el intervalo puro."""

    id: UUID
    empleado_id: UUID
    turno: Turno


def validar_sin_solapamientos(turnos: list[Turno]) -> None:
    """Rechaza turnos del mismo empleado que se solapan en el tiempo."""
    intervalos = sorted(t.intervalo() for t in turnos)
    for (_, fin_a), (inicio_b, _) in zip(intervalos, intervalos[1:]):
        if inicio_b < fin_a:
            raise ValueError(f"Turnos solapados: uno termina {fin_a} y otro inicia {inicio_b}")
