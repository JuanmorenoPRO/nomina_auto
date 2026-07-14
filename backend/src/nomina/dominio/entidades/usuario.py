from __future__ import annotations

import enum
from dataclasses import dataclass
from uuid import UUID


class Rol(enum.Enum):
    """Roles del sistema. Jerárquicos: admin ⊇ contadora ⊇ operador."""

    OPERADOR = "operador"  # solo ingresar turnos (y consultar)
    CONTADORA = "contadora"  # además: liquidar, exportar, periodos y entidades
    ADMIN = "admin"  # además: parámetros legales, festivos y usuarios

    def al_menos(self, minimo: Rol) -> bool:
        rango = {Rol.OPERADOR: 1, Rol.CONTADORA: 2, Rol.ADMIN: 3}
        return rango[self] >= rango[minimo]


@dataclass(frozen=True)
class Usuario:
    """El hash de contraseña NO vive en el dominio: es detalle de infraestructura."""

    id: UUID
    email: str
    rol: Rol
    activo: bool = True
