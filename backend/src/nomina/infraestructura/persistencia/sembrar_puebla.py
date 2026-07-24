"""Carga la unidad EDIFICIO PUEBLA P.H con sus empleados, turnos y conceptos
manuales de la quincena 1–15 jul 2026 (idempotente: solo si aún no existe).

Uso:  uv run python -m nomina.infraestructura.persistencia.sembrar_puebla
"""

from __future__ import annotations

from uuid import uuid4

from sqlalchemy.orm import Session

from nomina import puebla
from nomina.aplicacion.casos_uso.liquidar_quincena import LiquidarQuincena
from nomina.dominio.entidades.empleado import Empleado
from nomina.dominio.entidades.periodo_liquidacion import PeriodoLiquidacion
from nomina.dominio.entidades.turno import TurnoRegistrado
from nomina.dominio.entidades.unidad_residencial import ConfiguracionUnidad, UnidadResidencial
from nomina.infraestructura.persistencia.repositorios import (
    RepositorioConceptosManualesSQL,
    RepositorioEmpleadosSQL,
    RepositorioFestivosSQL,
    RepositorioLiquidacionesSQL,
    RepositorioParametrosSQL,
    RepositorioPeriodosSQL,
    RepositorioTurnosSQL,
    RepositorioUnidadesSQL,
)


def sembrar_puebla(session: Session) -> str | None:
    """Crea Puebla y sus datos si no existe. Devuelve el id de la unidad creada, o None."""
    unidades = RepositorioUnidadesSQL(session)
    if any(u.nombre == puebla.NOMBRE_UNIDAD for u in unidades.listar()):
        return None

    unidad = UnidadResidencial(
        id=uuid4(),
        nombre=puebla.NOMBRE_UNIDAD,
        nit=puebla.NIT,
        descuenta_seguridad_social=True,
        config=ConfiguracionUnidad(
            estrategia_extras=puebla.ESTRATEGIA_EXTRAS,
            factores_override=dict(puebla.FACTORES_OVERRIDE),
            conceptos_fijos=(puebla.CUOTA_MANEJO,),  # se aplica a todos los empleados
        ),
    )
    unidades.guardar(unidad)

    # Periodo 1–15 jul 2026 (reutiliza el existente si ya está creado).
    periodos = RepositorioPeriodosSQL(session)
    periodo = periodos.que_contiene(puebla.PERIODO_INICIO)
    if periodo is None or periodo.fecha_fin != puebla.PERIODO_FIN:
        periodo = PeriodoLiquidacion(
            id=uuid4(), fecha_inicio=puebla.PERIODO_INICIO, fecha_fin=puebla.PERIODO_FIN
        )
        periodos.guardar(periodo)

    empleados_repo = RepositorioEmpleadosSQL(session)
    turnos_repo = RepositorioTurnosSQL(session)

    for nombre, documento, cargo in puebla.EMPLEADOS:
        empleado = Empleado(
            id=uuid4(),
            unidad_id=unidad.id,
            nombre=nombre,
            documento=documento,
            cargo=cargo,
            salario_base=puebla.SALARIO_BASICO,
        )
        empleados_repo.guardar(empleado)
        for turno in puebla.turnos_de(documento):
            turnos_repo.guardar(
                TurnoRegistrado(id=uuid4(), empleado_id=empleado.id, turno=turno)
            )
        # La cuota de manejo ya es un concepto fijo de la unidad: se aplica sola.

    return str(unidad.id)


def main() -> None:
    from nomina.infraestructura.persistencia.base import crear_engine, fabrica_sesiones

    engine = crear_engine()
    with fabrica_sesiones(engine)() as session:
        unidad_id = sembrar_puebla(session)
        if unidad_id is None:
            session.commit()
            print("Puebla ya existía: sin cambios.")
            return
        # Liquidar la quincena y mostrar el resumen por empleado.
        periodo = RepositorioPeriodosSQL(session).que_contiene(puebla.PERIODO_INICIO)
        caso = LiquidarQuincena(
            periodos=RepositorioPeriodosSQL(session),
            unidades=RepositorioUnidadesSQL(session),
            empleados=RepositorioEmpleadosSQL(session),
            turnos=RepositorioTurnosSQL(session),
            parametros=RepositorioParametrosSQL(session),
            festivos=RepositorioFestivosSQL(session),
            liquidaciones=RepositorioLiquidacionesSQL(session),
            conceptos_manuales=RepositorioConceptosManualesSQL(session),
        )
        from uuid import UUID

        liq = caso.ejecutar(periodo.id, UUID(unidad_id))
        session.commit()
        print(f"Puebla creada. Liquidación v{liq.version} ({liq.id}):")
        for le in liq.por_empleado:
            liq_emp = le.liquidacion
            print(
                f"  {le.empleado.nombre:26} devengado ${int(liq_emp.total_devengado):>12,}  "
                f"deducciones ${int(liq_emp.total_deducciones):>10,}  "
                f"neto ${int(liq_emp.neto_a_pagar):>12,}"
            )


if __name__ == "__main__":
    main()
