"""Carga los datos de DEMOSTRACIÓN (`nomina/demo.py`) en la base configurada.

Nombres, cédulas y horarios son ficticios: sirve para probar la aplicación y
para generar las capturas del manual de usuario sin exponer datos reales.

Idempotente: se puede correr las veces que haga falta. Crea lo que falte y
REEMPLAZA los turnos, conceptos manuales y ajustes de la quincena de la demo
(no los duplica).

Uso — SIEMPRE contra una base aparte, nunca contra la base de trabajo:

    cd backend
    export DATABASE_URL=sqlite:///./nomina_demo.sqlite3
    export NOMINA_ADMIN_PASSWORD='...'          # mínimo 10 caracteres
    uv run alembic upgrade head
    uv run python -m nomina.infraestructura.persistencia.sembrar_demo

Crea también el usuario administrador `demo@ejemplo.com` con la contraseña de
`NOMINA_ADMIN_PASSWORD` (nunca se escribe una contraseña en el código).
"""

from __future__ import annotations

import os
from collections.abc import Callable, Sequence
from datetime import date
from decimal import Decimal
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from nomina import demo as datos
from nomina.aplicacion.casos_uso.liquidar_quincena import LiquidarQuincena
from nomina.dominio.entidades.concepto_liquidado import ConceptoManualRegistrado
from nomina.dominio.entidades.empleado import Empleado
from nomina.dominio.entidades.periodo_liquidacion import EstadoPeriodo, PeriodoLiquidacion
from nomina.dominio.entidades.turno import Turno, TurnoRegistrado
from nomina.dominio.entidades.unidad_residencial import ConfiguracionUnidad, UnidadResidencial
from nomina.dominio.entidades.usuario import Rol
from nomina.infraestructura.persistencia.modelos import UsuarioModel
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
from nomina.infraestructura.persistencia.sembrar import sembrar_parametros
from nomina.infraestructura.seguridad.auth import crear_usuario

EMAIL_DEMO = "demo@ejemplo.com"


def _asegurar_unidad(
    session: Session,
    nombre: str,
    nit: str,
    *,
    descuenta_ss: bool,
    config: ConfiguracionUnidad,
) -> UnidadResidencial:
    repo = RepositorioUnidadesSQL(session)
    for existente in repo.listar():
        if existente.nombre == nombre:
            actualizada = UnidadResidencial(
                id=existente.id,
                nombre=nombre,
                nit=nit,
                descuenta_seguridad_social=descuenta_ss,
                config=config,
            )
            repo.guardar(actualizada)
            print(f"  ~ Unidad actualizada: {nombre}")
            return actualizada
    unidad = UnidadResidencial(
        id=uuid4(),
        nombre=nombre,
        nit=nit,
        descuenta_seguridad_social=descuenta_ss,
        config=config,
    )
    repo.guardar(unidad)
    print(f"  + Unidad creada: {nombre}")
    return unidad


def _asegurar_empleados(
    session: Session,
    unidad: UnidadResidencial,
    definiciones: Sequence[tuple[str, str, str, Decimal]],
) -> dict[str, Empleado]:
    repo = RepositorioEmpleadosSQL(session)
    existentes = {e.documento: e for e in repo.listar(unidad_id=unidad.id)}
    for nombre, documento, cargo, salario in definiciones:
        if documento in existentes:
            continue
        empleado = Empleado(
            id=uuid4(),
            unidad_id=unidad.id,
            nombre=nombre,
            documento=documento,
            cargo=cargo,
            salario_base=salario,
        )
        repo.guardar(empleado)
        existentes[documento] = empleado
        print(f"  + Empleado creado: {nombre}")
    return existentes


def _asegurar_periodo(session: Session, inicio: date, fin: date) -> PeriodoLiquidacion:
    periodos = RepositorioPeriodosSQL(session)
    periodo = periodos.que_contiene(inicio)
    if periodo is not None and periodo.fecha_fin != fin:
        raise ValueError(
            f"Ya existe un periodo que contiene {inicio} pero termina el "
            f"{periodo.fecha_fin} (se esperaba {fin})."
        )
    if periodo is None:
        periodo = PeriodoLiquidacion(id=uuid4(), fecha_inicio=inicio, fecha_fin=fin)
        periodos.guardar(periodo)
        print(f"  + Periodo creado: {inicio} → {fin}")
    return periodo


def _reemplazar_turnos(
    session: Session,
    periodo: PeriodoLiquidacion,
    empleados: dict[str, Empleado],
    turnos_de: Callable[[str], list[Turno]],
) -> int:
    repo = RepositorioTurnosSQL(session)
    total = 0
    for documento, empleado in empleados.items():
        for existente in repo.de_empleado_entre(empleado.id, periodo.fecha_inicio, periodo.fecha_fin):
            repo.eliminar(existente.id)
        for turno in turnos_de(documento):
            repo.guardar(TurnoRegistrado(id=uuid4(), empleado_id=empleado.id, turno=turno))
            total += 1
    return total


def _reemplazar_conceptos(
    session: Session, periodo: PeriodoLiquidacion, empleados: dict[str, Empleado]
) -> None:
    repo = RepositorioConceptosManualesSQL(session)
    for documento, empleado in empleados.items():
        for existente in repo.listar(empleado_id=empleado.id, periodo_id=periodo.id):
            repo.eliminar(existente.id)
        for concepto in datos.CONCEPTOS_MANUALES.get(documento, ()):
            repo.guardar(
                ConceptoManualRegistrado(
                    id=uuid4(),
                    empleado_id=empleado.id,
                    periodo_id=periodo.id,
                    concepto=concepto,
                )
            )


def _aplicar_ajustes(
    session: Session, periodo: PeriodoLiquidacion, empleados: dict[str, Empleado]
) -> None:
    repo = RepositorioAjustesQuincenaSQL(session)
    for documento, empleado in empleados.items():
        incompleta, sin_extras, auxilio = datos.AJUSTES.get(documento, (False, False, False))
        repo.marcar(
            empleado.id,
            periodo.id,
            quincena_incompleta=incompleta,
            sin_extras=sin_extras,
            auxilio_por_dias_laborados=auxilio,
        )


def _historial(session: Session, caso: LiquidarQuincena, unidad: UnidadResidencial) -> None:
    """Deja dos quincenas anteriores en estado `liquidado` y `cerrado`, para que
    el manual pueda mostrar las tres insignias de estado y sus acciones."""
    periodos = RepositorioPeriodosSQL(session)
    for (inicio, fin), estado in (
        (datos.PERIODO_LIQUIDADO, EstadoPeriodo.LIQUIDADO),
        (datos.PERIODO_CERRADO, EstadoPeriodo.CERRADO),
    ):
        periodo = _asegurar_periodo(session, inicio, fin)
        if periodo.estado is not EstadoPeriodo.ABIERTO:
            continue
        caso.ejecutar(periodo.id, unidad.id)
        # `con_estado` prohíbe salir de CERRADO, así que se pasa por LIQUIDADO.
        periodo = periodo.con_estado(EstadoPeriodo.LIQUIDADO)
        if estado is EstadoPeriodo.CERRADO:
            periodo = periodo.con_estado(EstadoPeriodo.CERRADO)
        periodos.guardar(periodo)
        print(f"  ~ Periodo {inicio} → {fin} marcado como {estado.value}")


def _asegurar_usuario_demo(session: Session) -> None:
    existente = session.scalars(
        select(UsuarioModel).where(UsuarioModel.email == EMAIL_DEMO)
    ).first()
    if existente is not None:
        print(f"  = Usuario ya existe: {EMAIL_DEMO}")
        return
    contrasena = os.environ.get("NOMINA_ADMIN_PASSWORD", "")
    if len(contrasena) < 10:
        raise SystemExit(
            "Defina NOMINA_ADMIN_PASSWORD (mínimo 10 caracteres) para crear el usuario de la demo."
        )
    crear_usuario(session, EMAIL_DEMO, contrasena, Rol.ADMIN)
    print(f"  + Usuario creado: {EMAIL_DEMO} (admin)")


def main() -> None:
    from nomina.infraestructura.persistencia.base import crear_engine, fabrica_sesiones

    engine = crear_engine()
    with fabrica_sesiones(engine)() as session:
        print("=== Parámetros legales ===")
        sembrar_parametros(session)

        print("\n=== Usuario ===")
        _asegurar_usuario_demo(session)

        print("\n=== Unidades ===")
        unidad = _asegurar_unidad(
            session,
            datos.NOMBRE_UNIDAD,
            datos.NIT,
            descuenta_ss=True,
            config=ConfiguracionUnidad(
                estrategia_extras=datos.ESTRATEGIA_EXTRAS,
                factores_override=dict(datos.FACTORES_OVERRIDE),
                conceptos_fijos=datos.CONCEPTOS_FIJOS,
            ),
        )
        unidad_2 = _asegurar_unidad(
            session,
            datos.NOMBRE_UNIDAD_2,
            datos.NIT_2,
            descuenta_ss=False,
            config=ConfiguracionUnidad(),
        )

        print("\n=== Empleados ===")
        empleados = _asegurar_empleados(session, unidad, datos.EMPLEADOS)
        empleados_2 = _asegurar_empleados(session, unidad_2, datos.EMPLEADOS_2)

        print("\n=== Periodo ===")
        periodo = _asegurar_periodo(session, datos.PERIODO_INICIO, datos.PERIODO_FIN)

        print("\n=== Turnos, conceptos y ajustes ===")
        n1 = _reemplazar_turnos(session, periodo, empleados, datos.turnos_de)
        n2 = _reemplazar_turnos(session, periodo, empleados_2, datos.turnos_2_de)
        _reemplazar_conceptos(session, periodo, empleados)
        _aplicar_ajustes(session, periodo, empleados)
        print(f"  Turnos insertados: {n1} + {n2}")

        session.commit()

        print("\n=== Liquidación de prueba ===")
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
        _historial(session, caso, unidad)
        liq = caso.ejecutar(periodo.id, unidad.id)
        print(f"  {datos.NOMBRE_UNIDAD} (v{liq.version}):")
        for le in liq.por_empleado:
            print(
                f"    {le.empleado.nombre:24} devengado ${int(le.liquidacion.total_devengado):>12,}  "
                f"neto ${int(le.liquidacion.neto_a_pagar):>12,}"
            )
        session.commit()

    print(f"\n✅  Listo. Ingrese con {EMAIL_DEMO}.")


if __name__ == "__main__":
    main()
