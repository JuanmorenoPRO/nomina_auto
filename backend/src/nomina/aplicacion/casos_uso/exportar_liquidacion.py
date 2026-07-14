"""Caso de uso: exportar una liquidación a Excel (RF6)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol
from uuid import UUID

from nomina.aplicacion.casos_uso.liquidar_quincena import (
    LiquidacionQuincena,
    RepositorioLiquidaciones,
)
from nomina.aplicacion.errores import NoEncontradoError


class ExportadorLiquidacion(Protocol):
    def __call__(self, liquidacion: LiquidacionQuincena) -> bytes: ...


@dataclass(frozen=True)
class ExportarLiquidacion:
    liquidaciones: RepositorioLiquidaciones
    exportador: ExportadorLiquidacion

    def ejecutar(self, liquidacion_id: UUID) -> tuple[bytes, str]:
        """Devuelve (contenido, nombre de archivo)."""
        liquidacion = self.liquidaciones.obtener(liquidacion_id)
        if liquidacion is None:
            raise NoEncontradoError(f"No existe la liquidación {liquidacion_id}")
        nombre = (
            f"liquidacion_{liquidacion.unidad.nombre.replace(' ', '_')}"
            f"_{liquidacion.periodo.fecha_inicio:%Y-%m-%d}"
            f"_{liquidacion.periodo.fecha_fin:%Y-%m-%d}"
            f"_v{liquidacion.version}.xlsx"
        )
        return self.exportador(liquidacion), nombre
