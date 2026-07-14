from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from uuid import UUID


@dataclass(frozen=True)
class Empleado:
    """Datos sensibles (Ley 1581/2012): documento y salario. Acceso por rol en Fase 4."""

    id: UUID
    unidad_id: UUID
    nombre: str
    documento: str
    cargo: str
    salario_base: Decimal
    tipo_documento: str = "CC"
    activo: bool = True

    def __post_init__(self) -> None:
        if not self.nombre.strip():
            raise ValueError("El empleado debe tener nombre")
        if not self.documento.strip():
            raise ValueError("El empleado debe tener documento")
        if self.salario_base <= 0:
            raise ValueError("El salario base debe ser mayor que cero")
