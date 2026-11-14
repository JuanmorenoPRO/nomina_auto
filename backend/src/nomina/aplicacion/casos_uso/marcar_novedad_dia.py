"""Caso de uso: marcar la novedad de un día sin turno en el cuadro de turnos.

Un día sin turno es un descanso. Se puede marcar como `incapacidad` o
`no_laboro` (ver `dominio/valores/novedad_dia.py`); `None` lo devuelve a
descanso. Reglas: el empleado existe; la fecha cae en un periodo ABIERTO (una
quincena liquidada o cerrada no se toca); y el día NO tiene turnos — un día
trabajado no puede estar incapacitado.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Protocol
from uuid import UUID

from nomina.aplicacion.errores import NoEncontradoError, ReglaDeNegocioError
from nomina.dominio.entidades.periodo_liquidacion import EstadoPeriodo
from nomina.dominio.puertos.repositorios import (
    RepositorioEmpleados,
    RepositorioPeriodos,
    RepositorioTurnos,
)
from nomina.dominio.valores.novedad_dia import TIPOS_NOVEDAD_DIA


class RepositorioMarcarNovedadDia(Protocol):
    def marcar(self, empleado_id: UUID, fecha: date, tipo: str | None) -> None: ...


@dataclass(frozen=True)
class MarcarNovedadDia:
    empleados: RepositorioEmpleados
    periodos: RepositorioPeriodos
    turnos: RepositorioTurnos
    novedades: RepositorioMarcarNovedadDia

    def ejecutar(self, empleado_id: UUID, fecha: date, tipo: str | None) -> None:
        if tipo is not None and tipo not in TIPOS_NOVEDAD_DIA:
            raise ReglaDeNegocioError(f"Novedad de día desconocida: {tipo}")
        if self.empleados.obtener(empleado_id) is None:
            raise NoEncontradoError(f"No existe el empleado {empleado_id}")

        periodo = self.periodos.que_contiene(fecha)
        if periodo is None:
            raise ReglaDeNegocioError(f"No hay periodo de liquidación que contenga {fecha}")
        if periodo.estado is not EstadoPeriodo.ABIERTO:
            raise ReglaDeNegocioError(
                f"El periodo {periodo.fecha_inicio}–{periodo.fecha_fin} está "
                f"{periodo.estado.value}: reábralo para corregir el cuadro de turnos"
            )
        # Quitar la marca siempre se permite (deja el día limpio para registrar el turno).
        if tipo is not None and self.turnos.de_empleado_entre(empleado_id, fecha, fecha):
            raise ReglaDeNegocioError(
                f"El {fecha} tiene turnos registrados: quítelos antes de marcar el día"
            )
        self.novedades.marcar(empleado_id, fecha, tipo)
