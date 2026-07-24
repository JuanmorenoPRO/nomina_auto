"""Caso de uso: liquidar la quincena de una unidad residencial.

Segmenta y clasifica los turnos de cada empleado activo de la unidad, calcula
los conceptos y persiste una liquidación VERSIONADA con snapshot de los
parámetros usados. Reliquidar nunca sobrescribe: crea la versión siguiente.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from typing import Protocol
from uuid import UUID, uuid4

from nomina.aplicacion.errores import NoEncontradoError, ReglaDeNegocioError
from nomina.dominio.entidades.concepto_liquidado import ConceptoManual, Liquidacion
from nomina.dominio.entidades.empleado import Empleado
from nomina.dominio.entidades.parametro_legal import ConjuntoParametros
from nomina.dominio.entidades.periodo_liquidacion import EstadoPeriodo, PeriodoLiquidacion
from nomina.dominio.entidades.unidad_residencial import UnidadResidencial
from nomina.dominio.puertos.repositorios import (
    RepositorioEmpleados,
    RepositorioFestivos,
    RepositorioParametros,
    RepositorioPeriodos,
    RepositorioTurnos,
    RepositorioUnidades,
)
from nomina.dominio.servicios.calculadora import liquidar
from nomina.dominio.servicios.calendario_festivos import CalendarioFestivos
from nomina.dominio.servicios.clasificador_extras import clasificar_extras
from nomina.dominio.servicios.segmentador import segmentar_turnos


@dataclass(frozen=True)
class LiquidacionEmpleado:
    empleado: Empleado
    liquidacion: Liquidacion


@dataclass(frozen=True)
class LiquidacionQuincena:
    id: UUID
    periodo: PeriodoLiquidacion
    unidad: UnidadResidencial
    version: int
    creada_en: datetime
    por_empleado: tuple[LiquidacionEmpleado, ...]

    @property
    def total(self) -> Decimal:
        return sum((le.liquidacion.total for le in self.por_empleado), Decimal(0))


class RepositorioLiquidaciones(Protocol):
    """Puerto de la aplicación: persistir/leer liquidaciones versionadas."""

    def guardar(self, liquidacion: LiquidacionQuincena, parametros_snapshot: list[dict]) -> None: ...
    def obtener(self, id: UUID) -> LiquidacionQuincena | None: ...
    def listar(self, periodo_id: UUID | None = None) -> list[LiquidacionQuincena]: ...
    def ultima_version(self, periodo_id: UUID, unidad_id: UUID) -> int: ...


class RepositorioConceptosManuales(Protocol):
    """Puerto: conceptos manuales (devengados/deducciones) por empleado y periodo."""

    def de_empleado_en_periodo(
        self, empleado_id: UUID, periodo_id: UUID
    ) -> list[ConceptoManual]: ...


@dataclass(frozen=True)
class LiquidarQuincena:
    periodos: RepositorioPeriodos
    unidades: RepositorioUnidades
    empleados: RepositorioEmpleados
    turnos: RepositorioTurnos
    parametros: RepositorioParametros
    festivos: RepositorioFestivos
    liquidaciones: RepositorioLiquidaciones
    conceptos_manuales: RepositorioConceptosManuales

    def ejecutar(self, periodo_id: UUID, unidad_id: UUID) -> LiquidacionQuincena:
        periodo = self.periodos.obtener(periodo_id)
        if periodo is None:
            raise NoEncontradoError(f"No existe el periodo {periodo_id}")
        if periodo.estado is EstadoPeriodo.CERRADO:
            raise ReglaDeNegocioError("El periodo está cerrado: solo lectura")
        unidad = self.unidades.obtener(unidad_id)
        if unidad is None:
            raise NoEncontradoError(f"No existe la unidad {unidad_id}")

        lista_parametros = self.parametros.listar()
        conjunto = ConjuntoParametros(parametros=tuple(lista_parametros))
        agregados, anulados = self.festivos.ajustes()
        calendario = CalendarioFestivos(festivos_manuales=agregados, no_festivos=anulados)

        empleados = self.empleados.listar(unidad_id=unidad_id, solo_activos=True)
        if not empleados:
            raise ReglaDeNegocioError("La unidad no tiene empleados activos")

        por_empleado = []
        for empleado in empleados:
            registrados = self.turnos.de_empleado_entre(
                empleado.id, periodo.fecha_inicio, periodo.fecha_fin
            )
            tramos = segmentar_turnos([r.turno for r in registrados], conjunto, calendario)
            clasificados = clasificar_extras(
                tramos, conjunto, periodo.fecha_inicio, estrategia=unidad.config.estrategia_extras
            )
            # Conceptos fijos de la unidad (ej. cuota de manejo) + manuales del empleado.
            manuales = unidad.config.conceptos_fijos + tuple(
                self.conceptos_manuales.de_empleado_en_periodo(empleado.id, periodo_id)
            )
            resultado = liquidar(
                clasificados,
                empleado.salario_base,
                conjunto,
                periodo.fecha_inicio,
                factores_override=unidad.config.factores_override,
                conceptos_manuales=manuales,
                descontar_seguridad_social=unidad.descuenta_seguridad_social,
            )
            por_empleado.append(LiquidacionEmpleado(empleado=empleado, liquidacion=resultado))

        liquidacion = LiquidacionQuincena(
            id=uuid4(),
            periodo=periodo,
            unidad=unidad,
            version=self.liquidaciones.ultima_version(periodo_id, unidad_id) + 1,
            creada_en=datetime.now(UTC),
            por_empleado=tuple(por_empleado),
        )
        snapshot = [
            {
                "codigo": p.codigo,
                "valor": p.valor,
                "vigente_desde": p.vigencia.desde.isoformat(),
                "vigente_hasta": p.vigencia.hasta.isoformat() if p.vigencia.hasta else None,
                "norma": p.norma,
            }
            for p in lista_parametros
        ]
        self.liquidaciones.guardar(liquidacion, snapshot)
        self.periodos.guardar(periodo.con_estado(EstadoPeriodo.LIQUIDADO))
        return liquidacion
