"""Caso de uso: registrar un turno en la grilla quincenal.

Reglas: el empleado existe y está activo; la fecha cae en un periodo ABIERTO
(si ya se liquidó, hay que reabrirlo — la corrección generará otra versión);
el turno no se solapa con otros turnos del mismo empleado (incluidos los de
días vecinos que cruzan medianoche).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, time, timedelta
from uuid import UUID, uuid4

from nomina.aplicacion.errores import NoEncontradoError, ReglaDeNegocioError
from nomina.dominio.entidades.periodo_liquidacion import EstadoPeriodo
from nomina.dominio.entidades.turno import Turno, TurnoRegistrado, validar_sin_solapamientos
from nomina.dominio.puertos.repositorios import (
    RepositorioEmpleados,
    RepositorioPeriodos,
    RepositorioTurnos,
)


@dataclass(frozen=True)
class RegistrarTurno:
    empleados: RepositorioEmpleados
    periodos: RepositorioPeriodos
    turnos: RepositorioTurnos

    def ejecutar(
        self, empleado_id: UUID, fecha: date, hora_inicio: time, hora_fin: time
    ) -> TurnoRegistrado:
        empleado = self.empleados.obtener(empleado_id)
        if empleado is None:
            raise NoEncontradoError(f"No existe el empleado {empleado_id}")
        if not empleado.activo:
            raise ReglaDeNegocioError("El empleado está inactivo")

        periodo = self.periodos.que_contiene(fecha)
        if periodo is None:
            raise ReglaDeNegocioError(f"No hay periodo de liquidación que contenga {fecha}")
        if periodo.estado is not EstadoPeriodo.ABIERTO:
            raise ReglaDeNegocioError(
                f"El periodo {periodo.fecha_inicio}–{periodo.fecha_fin} está "
                f"{periodo.estado.value}: reábralo para corregir turnos"
            )

        turno = Turno(fecha=fecha, hora_inicio=hora_inicio, hora_fin=hora_fin)
        vecinos = self.turnos.de_empleado_entre(
            empleado_id, fecha - timedelta(days=1), fecha + timedelta(days=1)
        )
        try:
            validar_sin_solapamientos([v.turno for v in vecinos] + [turno])
        except ValueError as e:
            raise ReglaDeNegocioError(str(e)) from e

        registrado = TurnoRegistrado(id=uuid4(), empleado_id=empleado_id, turno=turno)
        self.turnos.guardar(registrado)
        return registrado
