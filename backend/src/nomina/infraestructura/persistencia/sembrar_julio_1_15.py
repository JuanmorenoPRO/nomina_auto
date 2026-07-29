"""Carga/corrige la quincena 1-15 jul 2026 para las 8 unidades cuya planilla real
llegó en Excel esta vez: SANTA RITA, CASA BLANCA, SUIZA, RIO CLARO, LORENA,
DEL VALLE y ALTO VERDE (Puebla ya se sembró aparte con `sembrar_puebla`).

Objetivo: que `total_devengado` de esta quincena en la BD coincida con la
planilla real de la contadora, para que la exportación de la quincena 16-30
sume bien las apropiaciones de seguridad social (`_hoja_apropiaciones` usa
`total_devengado` de ambas quincenas). Los turnos NO son el horario real: están
reconstruidos para que el motor reproduzca el TOTAL de horas por concepto. Ver
`nomina/julio_1_15.py` para el detalle y los huecos conocidos (aceptados).

Idempotente: se puede correr varias veces — crea las unidades/empleados que
falten, y siempre REEMPLAZA los turnos y conceptos manuales de este periodo
para estos empleados (no duplica).

Uso:
  uv run python -m nomina.infraestructura.persistencia.sembrar_julio_1_15
"""

from __future__ import annotations

from uuid import uuid4

from sqlalchemy.orm import Session

from nomina import julio_1_15 as datos
from nomina.aplicacion.casos_uso.liquidar_quincena import LiquidarQuincena
from nomina.dominio.entidades.concepto_liquidado import ConceptoManualRegistrado
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
from nomina.infraestructura.persistencia.sembrar_unidades import sembrar_unidades

# (nombre_unidad, nit, descuenta_seguridad_social, [(nombre_empleado, documento, cargo), ...])
UNIDADES_NUEVAS: list[tuple[str, str, bool, list[tuple[str, str, str]]]] = [
    (
        datos.SANTA_RITA_NOMBRE, datos.SANTA_RITA_NIT, True,
        [("GABRIEL JOAQUIN TORRES TORRES", "98567498-2", "empleado")],
    ),
    (
        # descuenta_seguridad_social=False: Doris no se descuenta pensión (trámite de
        # jubilación); la salud se carga como deducción manual en `julio_1_15.py`.
        datos.CASA_BLANCA_NOMBRE, datos.CASA_BLANCA_NIT, False,
        [("DORIS CECILIA BOLIVAR ESPINOSA", "43321643", "empleado")],
    ),
]

# Todas las unidades que este script puede crear/tocar (config, turnos, liquidación).
# Nunca toca unidades fuera de esta lista (ej. Puebla, Thunapa, Demo).
NOMBRES_EN_ALCANCE = {n for n, _, _, _ in UNIDADES_NUEVAS} | {
    "PARCELACION LA SUIZA P.H", "EDIFICIO RIO CLARO P.H", "EDIFICIO LORENA P.H",
    "EDIFICIO DEL VALLE P.H", "EDIFICIO ALTO VERDE P.H",
}

# descuenta_seguridad_social esperado por unidad en alcance, si difiere de True (el
# default de `sembrar_unidades`/`_crear_unidades_nuevas`).
DESCUENTA_SS_OVERRIDE: dict[str, bool] = {datos.CASA_BLANCA_NOMBRE: False}


def _config_unidad() -> ConfiguracionUnidad:
    return ConfiguracionUnidad(
        estrategia_extras=datos.ESTRATEGIA_EXTRAS,
        factores_override=dict(datos.FACTORES_OVERRIDE),
    )


def _crear_unidades_nuevas(session: Session) -> int:
    unidades_repo = RepositorioUnidadesSQL(session)
    empleados_repo = RepositorioEmpleadosSQL(session)
    existentes = {u.nombre for u in unidades_repo.listar()}
    creados = 0
    for nombre, nit, descuenta_ss, empleados in UNIDADES_NUEVAS:
        if nombre in existentes:
            continue
        unidad = UnidadResidencial(
            id=uuid4(), nombre=nombre, nit=nit,
            descuenta_seguridad_social=descuenta_ss, config=_config_unidad(),
        )
        unidades_repo.guardar(unidad)
        for nombre_emp, documento, cargo in empleados:
            empleados_repo.guardar(
                Empleado(
                    id=uuid4(), unidad_id=unidad.id, nombre=nombre_emp,
                    documento=documento, cargo=cargo, salario_base=datos.SALARIO_BASICO,
                )
            )
            creados += 1
        print(f"  + Unidad creada: {nombre} ({len(empleados)} empleados)")
    return creados


def _asegurar_config_unidades_existentes(session: Session) -> None:
    """Todas las unidades en alcance (nuevas o ya existentes) deben quedar con la
    misma config (factores legados + estrategia 'jornada') y el
    `descuenta_seguridad_social` correcto para que esta quincena cuadre con la
    planilla — `_crear_unidades_nuevas` solo aplica esto al CREAR, así que una
    unidad que ya existía (ej. Santa Rita, Casa Blanca en Railway) necesita este
    paso aparte."""
    unidades_repo = RepositorioUnidadesSQL(session)
    for unidad in unidades_repo.listar():
        if unidad.nombre not in NOMBRES_EN_ALCANCE:
            continue
        descuenta_ss = DESCUENTA_SS_OVERRIDE.get(unidad.nombre, True)
        config_ok = (
            unidad.config.estrategia_extras == datos.ESTRATEGIA_EXTRAS
            and unidad.config.factores_override == datos.FACTORES_OVERRIDE
        )
        if config_ok and unidad.descuenta_seguridad_social == descuenta_ss:
            continue
        actualizada = UnidadResidencial(
            id=unidad.id, nombre=unidad.nombre, nit=unidad.nit,
            descuenta_seguridad_social=descuenta_ss,
            config=_config_unidad(),
        )
        unidades_repo.guardar(actualizada)
        print(f"  ~ Config actualizada: {unidad.nombre}")


def _obtener_o_crear_periodo(session: Session) -> PeriodoLiquidacion:
    periodos = RepositorioPeriodosSQL(session)
    periodo = periodos.que_contiene(datos.PERIODO_INICIO)
    if periodo is not None and periodo.fecha_fin != datos.PERIODO_FIN:
        raise ValueError(
            f"Ya existe un periodo que contiene {datos.PERIODO_INICIO} pero con "
            f"fecha_fin {periodo.fecha_fin} (esperado {datos.PERIODO_FIN})."
        )
    if periodo is None:
        periodo = PeriodoLiquidacion(
            id=uuid4(), fecha_inicio=datos.PERIODO_INICIO, fecha_fin=datos.PERIODO_FIN
        )
        periodos.guardar(periodo)
    return periodo


def _cargar_turnos_y_conceptos(session: Session, periodo: PeriodoLiquidacion) -> int:
    unidades_repo = RepositorioUnidadesSQL(session)
    empleados_repo = RepositorioEmpleadosSQL(session)
    turnos_repo = RepositorioTurnosSQL(session)
    conceptos_repo = RepositorioConceptosManualesSQL(session)

    documentos = set(datos.TURNOS) | set(datos.CONCEPTOS_MANUALES)
    empleados_por_doc: dict[str, Empleado] = {}
    for unidad in unidades_repo.listar():
        for emp in empleados_repo.listar(unidad_id=unidad.id):
            if emp.documento in documentos:
                empleados_por_doc[emp.documento] = emp

    turnos_creados = 0
    for documento in documentos:
        empleado = empleados_por_doc.get(documento)
        if empleado is None:
            print(f"  [AVISO] Empleado doc {documento} no encontrado en ninguna unidad — se salta")
            continue

        # Reemplaza turnos existentes de este periodo (idempotente).
        for existente in turnos_repo.de_empleado_entre(empleado.id, periodo.fecha_inicio, periodo.fecha_fin):
            turnos_repo.eliminar(existente.id)
        for turno in datos.turnos_de(documento):
            turnos_repo.guardar(TurnoRegistrado(id=uuid4(), empleado_id=empleado.id, turno=turno))
            turnos_creados += 1

        # Reemplaza conceptos manuales existentes de este periodo (idempotente).
        for existente in conceptos_repo.listar(empleado_id=empleado.id, periodo_id=periodo.id):
            conceptos_repo.eliminar(existente.id)
        for concepto in datos.CONCEPTOS_MANUALES.get(documento, ()):
            conceptos_repo.guardar(
                ConceptoManualRegistrado(
                    id=uuid4(), empleado_id=empleado.id, periodo_id=periodo.id, concepto=concepto
                )
            )

    return turnos_creados


def main() -> None:
    from nomina.infraestructura.persistencia.base import crear_engine, fabrica_sesiones

    engine = crear_engine()
    with fabrica_sesiones(engine)() as session:
        print("=== Unidades base (SUIZA, RIO CLARO, LORENA, DEL VALLE, ALTO VERDE) ===")
        creadas, empleados_creados = sembrar_unidades(session)
        print(f"  Unidades creadas: {len(creadas)}  Empleados creados: {empleados_creados}")

        print("\n=== Unidades nuevas (SANTA RITA, CASA BLANCA) ===")
        nuevos = _crear_unidades_nuevas(session)
        print(f"  Empleados creados: {nuevos}" if nuevos else "  (ninguna unidad nueva necesaria)")

        print("\n=== Config de unidades (factores legados + estrategia 'jornada') ===")
        _asegurar_config_unidades_existentes(session)

        print("\n=== Periodo ===")
        periodo = _obtener_o_crear_periodo(session)
        print(f"  Periodo: {periodo.fecha_inicio} → {periodo.fecha_fin} (estado: {periodo.estado.value})")

        print("\n=== Turnos y conceptos manuales ===")
        turnos_creados = _cargar_turnos_y_conceptos(session, periodo)
        print(f"  Turnos insertados: {turnos_creados}")

        session.commit()

        print("\n=== Liquidando y verificando total_devengado por empleado ===")
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
        unidades_repo = RepositorioUnidadesSQL(session)
        for unidad in unidades_repo.listar():
            if unidad.nombre not in NOMBRES_EN_ALCANCE:
                continue  # no re-liquidar unidades fuera del alcance de este script (ej. Puebla)
            empleados = RepositorioEmpleadosSQL(session).listar(unidad_id=unidad.id)
            if not empleados:
                continue
            try:
                liq = caso.ejecutar(periodo.id, unidad.id)
            except Exception as e:  # unidad sin turnos en este periodo, etc.
                print(f"  [AVISO] {unidad.nombre}: {e}")
                continue
            print(f"  {unidad.nombre} (v{liq.version}):")
            for le in liq.por_empleado:
                print(f"    {le.empleado.nombre:32} devengado ${int(le.liquidacion.total_devengado):>12,}")
        session.commit()

    print("\n✅  Listo.")


if __name__ == "__main__":
    main()
