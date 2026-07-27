"""Caso de uso: marcar TODO el periodo como liquidado.

Liquidar una unidad ya no cierra el periodo (así se pueden liquidar varias
unidades del mismo periodo sin reabrir). Cuando la contadora terminó con todas
las unidades, marca el periodo completo como liquidado con este paso explícito.
Requiere al menos una liquidación existente en el periodo.
"""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from nomina.aplicacion.casos_uso.liquidar_quincena import RepositorioLiquidaciones
from nomina.aplicacion.errores import NoEncontradoError, ReglaDeNegocioError
from nomina.dominio.entidades.periodo_liquidacion import EstadoPeriodo, PeriodoLiquidacion
from nomina.dominio.puertos.repositorios import RepositorioPeriodos


@dataclass(frozen=True)
class MarcarPeriodoLiquidado:
    periodos: RepositorioPeriodos
    liquidaciones: RepositorioLiquidaciones

    def ejecutar(self, periodo_id: UUID) -> PeriodoLiquidacion:
        periodo = self.periodos.obtener(periodo_id)
        if periodo is None:
            raise NoEncontradoError(f"No existe el periodo {periodo_id}")
        if periodo.estado is EstadoPeriodo.CERRADO:
            raise ReglaDeNegocioError("El periodo está cerrado: solo lectura")
        if periodo.estado is EstadoPeriodo.LIQUIDADO:
            return periodo
        if not self.liquidaciones.listar(periodo_id):
            raise ReglaDeNegocioError(
                "Liquide al menos una unidad antes de marcar el periodo como liquidado"
            )
        marcado = periodo.con_estado(EstadoPeriodo.LIQUIDADO)
        self.periodos.guardar(marcado)
        return marcado
