"""Caso de uso: liquidar la quincena de una unidad residencial.

Segmenta y clasifica los turnos de cada empleado activo de la unidad, calcula
los conceptos y persiste una liquidación VERSIONADA con snapshot de los
parámetros usados. Reliquidar nunca sobrescribe: crea la versión siguiente.

Liquidar una unidad NO cierra el periodo: este queda ABIERTO para poder
liquidar otras unidades o corregir turnos sin reabrir. Marcar todo el periodo
como liquidado es un paso explícito aparte (ver `MarcarPeriodoLiquidado`).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
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
from nomina.dominio.servicios.clasificador_extras import (
    PRESUPUESTO_QUINCENAL,
    SEMANAL_LEGAL,
    clasificar_extras,
)
from nomina.dominio.servicios.segmentador import segmentar_turnos
from nomina.dominio.valores.tramo import Tramo


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


class RepositorioAjustesQuincena(Protocol):
    """Puerto: marcas manuales por empleado y periodo desde el cuadro de turnos.

    - `quincena_incompleta`: el empleado no laboró todas las horas (incapacidad,
      ausencia, ingreso/retiro a mitad de periodo).
    - `sin_extras`: no calcular horas extra por turno; solo cobrar extra sobre el
      excedente del presupuesto quincenal (el empleado concentró horas para
      descansar otros días sin superar el tope de la quincena).
    - `auxilio_por_dias_laborados`: prorratear el auxilio de transporte en
      proporción a lo laborado en vez de pagar el quincenal plano.
    - `pagar_dia_31`: reconocer aparte las horas no-extra del día 31, que el
      presupuesto de 15 días de la quincena no cubre."""

    def quincena_incompleta(self, empleado_id: UUID, periodo_id: UUID) -> bool: ...
    def sin_extras(self, empleado_id: UUID, periodo_id: UUID) -> bool: ...
    def auxilio_por_dias_laborados(self, empleado_id: UUID, periodo_id: UUID) -> bool: ...
    def pagar_dia_31(self, empleado_id: UUID, periodo_id: UUID) -> bool: ...


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
    ajustes_quincena: RepositorioAjustesQuincena

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
            # Si se marcó "sin extras" para este empleado en esta quincena, se
            # fuerza la clasificación por presupuesto quincenal (extra solo sobre
            # el excedente del tope legal), ignorando la estrategia de la unidad.
            sin_extras = self.ajustes_quincena.sin_extras(empleado.id, periodo_id)
            estrategia = (
                PRESUPUESTO_QUINCENAL if sin_extras else unidad.config.estrategia_extras
            )
            contexto = self._tramos_semana_previa(
                empleado.id, periodo, estrategia, conjunto, calendario
            )
            clasificados = clasificar_extras(
                tramos,
                conjunto,
                periodo.fecha_inicio,
                estrategia=estrategia,
                tramos_contexto=contexto,
            )
            # Conceptos fijos de la unidad (ej. cuota de manejo) + manuales del empleado.
            manuales = unidad.config.conceptos_fijos + tuple(
                self.conceptos_manuales.de_empleado_en_periodo(empleado.id, periodo_id)
            )
            incompleta = self.ajustes_quincena.quincena_incompleta(empleado.id, periodo_id)
            # El prorrateo del auxilio lo hace el dominio sobre las horas no-extra
            # efectivamente laboradas; aquí solo se transmite la marca.
            por_dias = self.ajustes_quincena.auxilio_por_dias_laborados(empleado.id, periodo_id)
            # El día 31 queda fuera del presupuesto (la quincena se paga como 15 días);
            # el dominio decide qué horas de ese día reconocer.
            dia_31 = self.ajustes_quincena.pagar_dia_31(empleado.id, periodo_id)
            resultado = liquidar(
                clasificados,
                empleado.salario_base,
                conjunto,
                periodo.fecha_inicio,
                # La marca manual manda: prorratear paga el auxilio aunque el empleado
                # esté incapacitado u ocasional (se incapacitó a mitad de quincena, pero
                # alcanzó a trabajar unos días y esos sí generan auxilio).
                incluir_auxilio_transporte=por_dias
                or not (empleado.incapacitado or empleado.ocasional),
                auxilio_prorrateado=por_dias,
                factores_override=unidad.config.factores_override,
                conceptos_manuales=manuales,
                descontar_seguridad_social=unidad.descuenta_seguridad_social,
                quincena_completa=not incompleta,
                pagar_dia_31=dia_31,
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
        return liquidacion

    def _tramos_semana_previa(
        self,
        empleado_id: UUID,
        periodo: PeriodoLiquidacion,
        estrategia: str,
        parametros: ConjuntoParametros,
        calendario: CalendarioFestivos,
    ) -> list[Tramo]:
        """Tramos de la misma semana ISO que quedaron antes del inicio del periodo.

        `semanal_legal` mide contra la jornada máxima SEMANAL, y la semana no se
        parte donde se parte la quincena: si el periodo arranca un miércoles, lo
        trabajado el lunes y el martes ya gastó presupuesto de esa semana y se
        pagó en la quincena anterior. Estos tramos solo alimentan el acumulado;
        no se liquidan aquí. Las demás estrategias tienen umbral por turno, por
        día o por periodo y no necesitan mirar hacia atrás.
        """
        if estrategia != SEMANAL_LEGAL:
            return []
        lunes = periodo.fecha_inicio - timedelta(days=periodo.fecha_inicio.weekday())
        # Un día más atrás que el lunes: el turno del domingo anterior que cruza
        # medianoche deja tramos en el lunes, y esos sí son de esta semana. Los
        # tramos que caen en la semana anterior van a un acumulado que nadie usa.
        previos = self.turnos.de_empleado_entre(
            empleado_id, lunes - timedelta(days=1), periodo.fecha_inicio - timedelta(days=1)
        )
        return segmentar_turnos([r.turno for r in previos], parametros, calendario)
