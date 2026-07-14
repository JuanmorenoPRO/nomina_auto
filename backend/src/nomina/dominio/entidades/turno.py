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
    """

    fecha: date
    hora_inicio: time
    hora_fin: time

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
