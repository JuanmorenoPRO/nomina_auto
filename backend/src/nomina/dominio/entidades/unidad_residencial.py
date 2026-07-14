from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True)
class UnidadResidencial:
    id: UUID
    nombre: str
    nit: str = ""
    activa: bool = True

    def __post_init__(self) -> None:
        if not self.nombre.strip():
            raise ValueError("La unidad residencial debe tener nombre")
