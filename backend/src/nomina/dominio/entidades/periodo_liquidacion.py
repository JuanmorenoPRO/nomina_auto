from __future__ import annotations

import enum
from dataclasses import dataclass, replace
from datetime import date
from uuid import UUID


class EstadoPeriodo(enum.Enum):
    ABIERTO = "abierto"
    LIQUIDADO = "liquidado"
    CERRADO = "cerrado"  # solo lectura definitiva (Fase 4)


@dataclass(frozen=True)
class PeriodoLiquidacion:
    """Quincena (o periodo) de liquidación, definido por fechas, no por regla fija."""

    id: UUID
    fecha_inicio: date
    fecha_fin: date
    estado: EstadoPeriodo = EstadoPeriodo.ABIERTO

    def __post_init__(self) -> None:
        if self.fecha_fin < self.fecha_inicio:
            raise ValueError(
                f"Periodo inválido: fin {self.fecha_fin} < inicio {self.fecha_inicio}"
            )

    def contiene(self, fecha: date) -> bool:
        return self.fecha_inicio <= fecha <= self.fecha_fin

    def con_estado(self, estado: EstadoPeriodo) -> PeriodoLiquidacion:
        if self.estado is EstadoPeriodo.CERRADO:
            raise ValueError("Un periodo cerrado es de solo lectura")
        return replace(self, estado=estado)
