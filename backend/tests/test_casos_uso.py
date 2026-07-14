"""Casos de uso contra la BD (SQLite en memoria)."""

from datetime import date, time
from decimal import Decimal
from uuid import uuid4

import pytest

from nomina.aplicacion.casos_uso.actualizar_parametro import ActualizarParametro
from nomina.aplicacion.casos_uso.liquidar_quincena import LiquidarQuincena
from nomina.aplicacion.casos_uso.registrar_turno import RegistrarTurno
from nomina.aplicacion.errores import NoEncontradoError, ReglaDeNegocioError
from nomina.dominio.entidades.empleado import Empleado
from nomina.dominio.entidades.periodo_liquidacion import EstadoPeriodo, PeriodoLiquidacion
from nomina.dominio.entidades.unidad_residencial import UnidadResidencial
from nomina.infraestructura.persistencia.repositorios import (
    RepositorioEmpleadosSQL,
    RepositorioFestivosSQL,
    RepositorioLiquidacionesSQL,
    RepositorioParametrosSQL,
    RepositorioPeriodosSQL,
    RepositorioTurnosSQL,
    RepositorioUnidadesSQL,
)


@pytest.fixture
def contexto(session):
    """Unidad + empleado (salario 2.2M → tarifa 10.000) + periodo 16–30 jun 2026."""
    unidad = UnidadResidencial(id=uuid4(), nombre="Edificio Prueba P.H.", nit="900000000")
    RepositorioUnidadesSQL(session).guardar(unidad)
    empleado = Empleado(
        id=uuid4(),
        unidad_id=unidad.id,
        nombre="FREDY PRUEBA",
        documento="71712119",
        cargo="vigilante",
        salario_base=Decimal(2_200_000),
    )
    RepositorioEmpleadosSQL(session).guardar(empleado)
    periodo = PeriodoLiquidacion(
        id=uuid4(), fecha_inicio=date(2026, 6, 16), fecha_fin=date(2026, 6, 30)
    )
    RepositorioPeriodosSQL(session).guardar(periodo)
    return unidad, empleado, periodo


def _registrar(session) -> RegistrarTurno:
    return RegistrarTurno(
        empleados=RepositorioEmpleadosSQL(session),
        periodos=RepositorioPeriodosSQL(session),
        turnos=RepositorioTurnosSQL(session),
    )


def _liquidar(session) -> LiquidarQuincena:
    return LiquidarQuincena(
        periodos=RepositorioPeriodosSQL(session),
        unidades=RepositorioUnidadesSQL(session),
        empleados=RepositorioEmpleadosSQL(session),
        turnos=RepositorioTurnosSQL(session),
        parametros=RepositorioParametrosSQL(session),
        festivos=RepositorioFestivosSQL(session),
        liquidaciones=RepositorioLiquidacionesSQL(session),
    )


def test_registrar_turno_valida_empleado_periodo_y_solapamientos(session, contexto):
    _, empleado, _ = contexto
    caso = _registrar(session)

    with pytest.raises(NoEncontradoError):
        caso.ejecutar(uuid4(), date(2026, 6, 20), time(6), time(18))
    with pytest.raises(ReglaDeNegocioError, match="No hay periodo"):
        caso.ejecutar(empleado.id, date(2026, 9, 1), time(6), time(18))

    caso.ejecutar(empleado.id, date(2026, 6, 20), time(18), time(6))  # cruza medianoche
    # el turno del día siguiente a las 05:00 se solapa con el anterior (termina 06:00)
    with pytest.raises(ReglaDeNegocioError, match="solapados"):
        caso.ejecutar(empleado.id, date(2026, 6, 21), time(5), time(14))
    # a las 06:00 en punto es contiguo, no solapado
    caso.ejecutar(empleado.id, date(2026, 6, 21), time(6), time(14))


def test_liquidar_quincena_caso_contadora_via_bd(session, contexto):
    """Golden 4 completo por la BD: dom 28-jun 18:00 → lun festivo 29-jun 06:00."""
    unidad, empleado, periodo = contexto
    _registrar(session).ejecutar(empleado.id, date(2026, 6, 28), time(18), time(6))

    liquidacion = _liquidar(session).ejecutar(periodo.id, unidad.id)

    assert liquidacion.version == 1
    (por_empleado,) = liquidacion.por_empleado
    valores = {c.codigo: c.valor for c in por_empleado.liquidacion.conceptos}
    assert valores["tiempo_ordinario"] == Decimal(1_100_000)
    assert valores["festivo_diurno"] == Decimal(18_000)
    assert valores["festivo_nocturno"] == Decimal(236_500)
    assert valores["auxilio_transporte"] == Decimal(124_548)
    assert por_empleado.liquidacion.total == Decimal(1_479_048)

    # el periodo quedó liquidado y la liquidación es recuperable tal cual
    assert RepositorioPeriodosSQL(session).obtener(periodo.id).estado is EstadoPeriodo.LIQUIDADO
    recuperada = RepositorioLiquidacionesSQL(session).obtener(liquidacion.id)
    assert recuperada.total == Decimal(1_479_048)
    assert recuperada.por_empleado[0].liquidacion.conceptos == por_empleado.liquidacion.conceptos


def test_reliquidar_crea_nueva_version_y_no_sobrescribe(session, contexto):
    unidad, empleado, periodo = contexto
    _registrar(session).ejecutar(empleado.id, date(2026, 6, 17), time(6), time(14))
    primera = _liquidar(session).ejecutar(periodo.id, unidad.id)

    # corregir exige reabrir el periodo (quedó liquidado)
    with pytest.raises(ReglaDeNegocioError, match="reábralo"):
        _registrar(session).ejecutar(empleado.id, date(2026, 6, 18), time(6), time(14))
    repo_periodos = RepositorioPeriodosSQL(session)
    repo_periodos.guardar(repo_periodos.obtener(periodo.id).con_estado(EstadoPeriodo.ABIERTO))
    _registrar(session).ejecutar(empleado.id, date(2026, 6, 18), time(6), time(14))

    segunda = _liquidar(session).ejecutar(periodo.id, unidad.id)
    assert segunda.version == 2
    # ambas versiones siguen consultables
    repo = RepositorioLiquidacionesSQL(session)
    assert {liq.version for liq in repo.listar(periodo_id=periodo.id)} == {1, 2}
    assert repo.obtener(primera.id) is not None


def test_liquidacion_guarda_snapshot_de_parametros(session, contexto):
    unidad, empleado, periodo = contexto
    _registrar(session).ejecutar(empleado.id, date(2026, 6, 17), time(6), time(14))
    liquidacion = _liquidar(session).ejecutar(periodo.id, unidad.id)

    from nomina.infraestructura.persistencia.modelos import LiquidacionModel

    modelo = session.get(LiquidacionModel, liquidacion.id)
    codigos = {p["codigo"] for p in modelo.parametros_snapshot}
    assert "recargo_dominical_festivo" in codigos
    assert len(modelo.parametros_snapshot) == 20


def test_actualizar_parametro_cierra_vigencia_anterior(session):
    repo = RepositorioParametrosSQL(session)
    caso = ActualizarParametro(parametros=repo)

    caso.ejecutar("recargo_nocturno", "0.40", date(2027, 1, 1), norma="reforma hipotética")

    vigencias = [p for p in repo.listar() if p.codigo == "recargo_nocturno"]
    assert len(vigencias) == 2
    anterior, nueva = vigencias
    assert anterior.vigencia.hasta == date(2026, 12, 31)
    assert nueva.valor == "0.40" and nueva.vigencia.hasta is None

    with pytest.raises(ReglaDeNegocioError, match="desconocido"):
        caso.ejecutar("parametro_inventado", "1", date(2027, 1, 1))
    with pytest.raises(ReglaDeNegocioError, match="debe iniciar después"):
        caso.ejecutar("recargo_nocturno", "0.45", date(2026, 1, 1))


def test_liquidar_usa_festivos_manuales(session, contexto):
    """Un día decretado festivo a última hora se agrega manualmente y el motor lo paga."""
    unidad, empleado, periodo = contexto
    RepositorioFestivosSQL(session).agregar_ajuste(date(2026, 6, 17), "día cívico", True)
    _registrar(session).ejecutar(empleado.id, date(2026, 6, 17), time(8), time(16))

    liquidacion = _liquidar(session).ejecutar(periodo.id, unidad.id)
    valores = {c.codigo: c.valor for c in liquidacion.por_empleado[0].liquidacion.conceptos}
    assert valores["festivo_diurno"] == Decimal(144_000)  # 8 h × 1,80 × 10.000
