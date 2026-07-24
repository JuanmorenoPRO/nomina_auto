"""Conversión de entidades de dominio a schemas de respuesta."""

from __future__ import annotations

from nomina.aplicacion.casos_uso.liquidar_quincena import LiquidacionQuincena
from nomina.dominio.entidades.empleado import Empleado
from nomina.dominio.entidades.periodo_liquidacion import PeriodoLiquidacion
from nomina.dominio.entidades.turno import TurnoRegistrado
from nomina.dominio.entidades.unidad_residencial import UnidadResidencial
from nomina.infraestructura.api.schemas import (
    ConceptoFijoConfig,
    ConceptoRespuesta,
    EmpleadoRespuesta,
    LiquidacionEmpleadoRespuesta,
    LiquidacionRespuesta,
    PeriodoRespuesta,
    TurnoRespuesta,
    UnidadConfig,
    UnidadRespuesta,
)


def unidad_a_schema(u: UnidadResidencial) -> UnidadRespuesta:
    return UnidadRespuesta(
        id=u.id,
        nombre=u.nombre,
        nit=u.nit,
        activa=u.activa,
        descuenta_seguridad_social=u.descuenta_seguridad_social,
        config=UnidadConfig(
            estrategia_extras=u.config.estrategia_extras,
            factores_override={k: str(v) for k, v in u.config.factores_override.items()},
            conceptos_fijos=[
                ConceptoFijoConfig(
                    nombre=c.nombre, valor=int(c.valor), tipo=c.tipo, salarial=c.salarial
                )
                for c in u.config.conceptos_fijos
            ],
        ),
    )


def empleado_a_schema(e: Empleado) -> EmpleadoRespuesta:
    return EmpleadoRespuesta(
        id=e.id,
        unidad_id=e.unidad_id,
        nombre=e.nombre,
        tipo_documento=e.tipo_documento,
        documento=e.documento,
        cargo=e.cargo,
        salario_base=int(e.salario_base),
        activo=e.activo,
    )


def periodo_a_schema(p: PeriodoLiquidacion) -> PeriodoRespuesta:
    return PeriodoRespuesta(
        id=p.id, fecha_inicio=p.fecha_inicio, fecha_fin=p.fecha_fin, estado=p.estado.value
    )


def turno_a_schema(t: TurnoRegistrado) -> TurnoRespuesta:
    return TurnoRespuesta(
        id=t.id,
        empleado_id=t.empleado_id,
        fecha=t.turno.fecha,
        hora_inicio=t.turno.hora_inicio,
        hora_fin=t.turno.hora_fin,
        cruza_medianoche=t.turno.hora_fin <= t.turno.hora_inicio,
    )


def liquidacion_a_schema(liq: LiquidacionQuincena) -> LiquidacionRespuesta:
    def _concepto(c) -> ConceptoRespuesta:
        return ConceptoRespuesta(
            codigo=c.codigo,
            nombre=c.nombre,
            minutos=c.minutos,
            horas=f"{c.horas:.2f}",
            factor=str(c.factor) if c.factor is not None else None,
            componentes={k: str(v) for k, v in c.componentes.items()},
            valor=int(c.valor),
        )

    empleados = [
        LiquidacionEmpleadoRespuesta(
            empleado_id=le.empleado.id,
            nombre=le.empleado.nombre,
            documento=le.empleado.documento,
            salario_mensual=int(le.liquidacion.salario_mensual),
            tarifa_hora=str(le.liquidacion.tarifa_hora),
            conceptos=[_concepto(c) for c in le.liquidacion.conceptos],
            deducciones=[_concepto(d) for d in le.liquidacion.deducciones],
            total_devengado=int(le.liquidacion.total_devengado),
            total_deducciones=int(le.liquidacion.total_deducciones),
            neto_a_pagar=int(le.liquidacion.neto_a_pagar),
            total=int(le.liquidacion.total),
        )
        for le in liq.por_empleado
    ]
    return LiquidacionRespuesta(
        id=liq.id,
        periodo=periodo_a_schema(liq.periodo),
        unidad=unidad_a_schema(liq.unidad),
        version=liq.version,
        creada_en=liq.creada_en,
        empleados=empleados,
        total=int(liq.total),
    )
