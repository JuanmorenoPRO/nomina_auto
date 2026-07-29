"""Carga/corrige EDIFICIO THUNAPA P.H (mayo 2026, dos quincenas) con sus
empleados, turnos y config. Idempotente: se puede correr varias veces.

A diferencia de `sembrar_puebla.py` (unidad nueva, create-only), Thunapa YA
EXISTE como fila vacía en Railway (`config` sin `estrategia_extras` ni
`factores_override`, sin empleados, sin periodos) — este seeder actualiza esa
unidad si ya existe, o la crea si no, siempre dejando la config correcta.
Siempre REEMPLAZA turnos y conceptos manuales de estas dos quincenas para
estos 4 empleados (no duplica). Ver `nomina/thunapa.py` para el detalle.

Uso:
  uv run python -m nomina.infraestructura.persistencia.sembrar_thunapa
"""

from __future__ import annotations

from uuid import uuid4

from sqlalchemy.orm import Session

from nomina import thunapa as datos
from nomina.aplicacion.casos_uso.liquidar_quincena import LiquidarQuincena
from nomina.dominio.entidades.concepto_liquidado import ConceptoManualRegistrado
from nomina.dominio.entidades.empleado import Empleado
from nomina.dominio.entidades.periodo_liquidacion import PeriodoLiquidacion
from nomina.dominio.entidades.turno import TurnoRegistrado
from nomina.dominio.entidades.unidad_residencial import ConfiguracionUnidad, UnidadResidencial
from nomina.infraestructura.persistencia.repositorios import (
    RepositorioAjustesQuincenaSQL,
    RepositorioConceptosManualesSQL,
    RepositorioEmpleadosSQL,
    RepositorioFestivosSQL,
    RepositorioLiquidacionesSQL,
    RepositorioParametrosSQL,
    RepositorioPeriodosSQL,
    RepositorioTurnosSQL,
    RepositorioUnidadesSQL,
)


def _config_thunapa() -> ConfiguracionUnidad:
    return ConfiguracionUnidad(
        estrategia_extras=datos.ESTRATEGIA_EXTRAS,
        factores_override=dict(datos.FACTORES_OVERRIDE),
    )


def _asegurar_unidad(session: Session) -> UnidadResidencial:
    """Crea la unidad si no existe; si existe, corrige su config/`descuenta_ss`
    (Thunapa en Railway quedó con config vacío antes de este seeder)."""
    repo = RepositorioUnidadesSQL(session)
    for existente in repo.listar():
        if existente.nombre == datos.NOMBRE_UNIDAD:
            config_ok = (
                existente.config.estrategia_extras == datos.ESTRATEGIA_EXTRAS
                and existente.config.factores_override == datos.FACTORES_OVERRIDE
            )
            if config_ok and existente.descuenta_seguridad_social is False:
                return existente
            actualizada = UnidadResidencial(
                id=existente.id, nombre=existente.nombre, nit=existente.nit,
                descuenta_seguridad_social=False, config=_config_thunapa(),
            )
            repo.guardar(actualizada)
            print(f"  ~ Config actualizada: {existente.nombre}")
            return actualizada
    unidad = UnidadResidencial(
        id=uuid4(), nombre=datos.NOMBRE_UNIDAD, nit=datos.NIT,
        descuenta_seguridad_social=False, config=_config_thunapa(),
    )
    repo.guardar(unidad)
    print(f"  + Unidad creada: {datos.NOMBRE_UNIDAD}")
    return unidad


def _asegurar_empleados(session: Session, unidad: UnidadResidencial) -> dict[str, Empleado]:
    empleados_repo = RepositorioEmpleadosSQL(session)
    existentes = {e.documento: e for e in empleados_repo.listar(unidad_id=unidad.id)}
    for nombre, documento, cargo in datos.EMPLEADOS:
        if documento in existentes:
            continue
        empleado = Empleado(
            id=uuid4(), unidad_id=unidad.id, nombre=nombre,
            documento=documento, cargo=cargo, salario_base=datos.SALARIO_BASICO,
        )
        empleados_repo.guardar(empleado)
        existentes[documento] = empleado
        print(f"  + Empleado creado: {nombre}")
    return existentes


def _asegurar_periodo(session: Session, inicio, fin) -> PeriodoLiquidacion:
    periodos = RepositorioPeriodosSQL(session)
    periodo = periodos.que_contiene(inicio)
    if periodo is not None and periodo.fecha_fin != fin:
        raise ValueError(
            f"Ya existe un periodo que contiene {inicio} pero con fecha_fin "
            f"{periodo.fecha_fin} (esperado {fin})."
        )
    if periodo is None:
        periodo = PeriodoLiquidacion(id=uuid4(), fecha_inicio=inicio, fecha_fin=fin)
        periodos.guardar(periodo)
        print(f"  + Periodo creado: {inicio} → {fin}")
    return periodo


def _reemplazar_turnos_y_conceptos(
    session: Session,
    periodo: PeriodoLiquidacion,
    empleados: dict[str, Empleado],
    turnos_de,
    conceptos_manuales: dict,
) -> int:
    turnos_repo = RepositorioTurnosSQL(session)
    conceptos_repo = RepositorioConceptosManualesSQL(session)
    total = 0
    for documento, empleado in empleados.items():
        for existente in turnos_repo.de_empleado_entre(empleado.id, periodo.fecha_inicio, periodo.fecha_fin):
            turnos_repo.eliminar(existente.id)
        for turno in turnos_de(documento):
            turnos_repo.guardar(TurnoRegistrado(id=uuid4(), empleado_id=empleado.id, turno=turno))
            total += 1

        for existente in conceptos_repo.listar(empleado_id=empleado.id, periodo_id=periodo.id):
            conceptos_repo.eliminar(existente.id)
        for concepto in conceptos_manuales.get(documento, ()):
            conceptos_repo.guardar(
                ConceptoManualRegistrado(
                    id=uuid4(), empleado_id=empleado.id, periodo_id=periodo.id, concepto=concepto
                )
            )
    return total


def main() -> None:
    from nomina.infraestructura.persistencia.base import crear_engine, fabrica_sesiones

    engine = crear_engine()
    with fabrica_sesiones(engine)() as session:
        print("=== Unidad ===")
        unidad = _asegurar_unidad(session)

        print("\n=== Empleados ===")
        empleados = _asegurar_empleados(session, unidad)

        print("\n=== Periodos ===")
        periodo_1 = _asegurar_periodo(session, datos.PERIODO_1_INICIO, datos.PERIODO_1_FIN)
        periodo_2 = _asegurar_periodo(session, datos.PERIODO_2_INICIO, datos.PERIODO_2_FIN)

        print("\n=== Turnos y conceptos manuales ===")
        n1 = _reemplazar_turnos_y_conceptos(
            session, periodo_1, empleados, datos.turnos_1_15_de, datos.CONCEPTOS_MANUALES_1_15
        )
        n2 = _reemplazar_turnos_y_conceptos(
            session, periodo_2, empleados, datos.turnos_16_31_de, datos.CONCEPTOS_MANUALES_16_31
        )
        print(f"  Turnos insertados: {n1} (1-15) + {n2} (16-31)")

        session.commit()

        print("\n=== Liquidando y verificando ===")
        caso = LiquidarQuincena(
            periodos=RepositorioPeriodosSQL(session),
            unidades=RepositorioUnidadesSQL(session),
            empleados=RepositorioEmpleadosSQL(session),
            turnos=RepositorioTurnosSQL(session),
            parametros=RepositorioParametrosSQL(session),
            festivos=RepositorioFestivosSQL(session),
            liquidaciones=RepositorioLiquidacionesSQL(session),
            conceptos_manuales=RepositorioConceptosManualesSQL(session),
            ajustes_quincena=RepositorioAjustesQuincenaSQL(session),
        )
        for nombre_periodo, periodo in (("1-15", periodo_1), ("16-31", periodo_2)):
            liq = caso.ejecutar(periodo.id, unidad.id)
            print(f"  Quincena {nombre_periodo} (v{liq.version}):")
            for le in liq.por_empleado:
                print(
                    f"    {le.empleado.nombre:32} devengado ${int(le.liquidacion.total_devengado):>12,}  "
                    f"neto ${int(le.liquidacion.neto_a_pagar):>12,}"
                )
        session.commit()

    print("\n✅  Listo.")


if __name__ == "__main__":
    main()
