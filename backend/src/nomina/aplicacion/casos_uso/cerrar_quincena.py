"""Caso de uso: cerrar definitivamente una quincena.

Solo se cierra un periodo ya LIQUIDADO. Un periodo CERRADO queda en solo
lectura para siempre: no se reabre, no acepta turnos ni reliquidaciones.
"""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from nomina.aplicacion.errores import NoEncontradoError, ReglaDeNegocioError
from nomina.dominio.entidades.periodo_liquidacion import EstadoPeriodo, PeriodoLiquidacion
from nomina.dominio.puertos.repositorios import RepositorioPeriodos


@dataclass(frozen=True)
class CerrarQuincena:
    periodos: RepositorioPeriodos

    def ejecutar(self, periodo_id: UUID) -> PeriodoLiquidacion:
        periodo = self.periodos.obtener(periodo_id)
        if periodo is None:
            raise NoEncontradoError(f"No existe el periodo {periodo_id}")
        if periodo.estado is not EstadoPeriodo.LIQUIDADO:
            raise ReglaDeNegocioError(
                "Solo se cierra un periodo liquidado; este está "
                f"{periodo.estado.value}"
            )
        cerrado = periodo.con_estado(EstadoPeriodo.CERRADO)
        self.periodos.guardar(cerrado)
        return cerrado
