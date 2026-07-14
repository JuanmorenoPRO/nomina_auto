"""Endpoints de la API (Fase 2 — sin autenticación todavía; roles en Fase 4)."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Annotated
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from sqlalchemy.orm import Session

from nomina.aplicacion.casos_uso.actualizar_parametro import ActualizarParametro
from nomina.aplicacion.casos_uso.exportar_liquidacion import ExportarLiquidacion
from nomina.aplicacion.casos_uso.liquidar_quincena import LiquidarQuincena
from nomina.aplicacion.casos_uso.registrar_turno import RegistrarTurno
from nomina.dominio.entidades.empleado import Empleado
from nomina.dominio.entidades.periodo_liquidacion import EstadoPeriodo, PeriodoLiquidacion
from nomina.dominio.entidades.unidad_residencial import UnidadResidencial
from nomina.dominio.servicios.calendario_festivos import festivos_por_ley
from nomina.infraestructura.api import schemas, traductores
from nomina.infraestructura.excel.exportador import exportar_liquidacion_excel
from nomina.infraestructura.persistencia.base import sesion
from nomina.infraestructura.persistencia.repositorios import (
    RepositorioEmpleadosSQL,
    RepositorioFestivosSQL,
    RepositorioLiquidacionesSQL,
    RepositorioParametrosSQL,
    RepositorioPeriodosSQL,
    RepositorioTurnosSQL,
    RepositorioUnidadesSQL,
)

Sesion = Annotated[Session, Depends(sesion)]

router = APIRouter()


@router.get("/salud")
def salud() -> dict[str, str]:
    return {"estado": "ok"}


# --- Unidades residenciales ---


@router.post("/unidades", response_model=schemas.UnidadRespuesta, status_code=201)
def crear_unidad(datos: schemas.UnidadCrear, session: Sesion):
    unidad = UnidadResidencial(id=uuid4(), nombre=datos.nombre, nit=datos.nit)
    RepositorioUnidadesSQL(session).guardar(unidad)
    return traductores.unidad_a_schema(unidad)


@router.get("/unidades", response_model=list[schemas.UnidadRespuesta])
def listar_unidades(session: Sesion):
    return [traductores.unidad_a_schema(u) for u in RepositorioUnidadesSQL(session).listar()]


# --- Empleados ---


@router.post("/empleados", response_model=schemas.EmpleadoRespuesta, status_code=201)
def crear_empleado(datos: schemas.EmpleadoCrear, session: Sesion):
    if RepositorioUnidadesSQL(session).obtener(datos.unidad_id) is None:
        raise HTTPException(404, "No existe la unidad residencial")
    empleado = Empleado(
        id=uuid4(),
        unidad_id=datos.unidad_id,
        nombre=datos.nombre,
        tipo_documento=datos.tipo_documento,
        documento=datos.documento,
        cargo=datos.cargo,
        salario_base=Decimal(datos.salario_base),
    )
    RepositorioEmpleadosSQL(session).guardar(empleado)
    return traductores.empleado_a_schema(empleado)


@router.get("/empleados", response_model=list[schemas.EmpleadoRespuesta])
def listar_empleados(session: Sesion, unidad_id: UUID | None = None):
    empleados = RepositorioEmpleadosSQL(session).listar(unidad_id=unidad_id)
    return [traductores.empleado_a_schema(e) for e in empleados]


# --- Periodos de liquidación ---


@router.post("/periodos", response_model=schemas.PeriodoRespuesta, status_code=201)
def crear_periodo(datos: schemas.PeriodoCrear, session: Sesion):
    periodo = PeriodoLiquidacion(
        id=uuid4(), fecha_inicio=datos.fecha_inicio, fecha_fin=datos.fecha_fin
    )
    RepositorioPeriodosSQL(session).guardar(periodo)
    return traductores.periodo_a_schema(periodo)


@router.get("/periodos", response_model=list[schemas.PeriodoRespuesta])
def listar_periodos(session: Sesion):
    return [traductores.periodo_a_schema(p) for p in RepositorioPeriodosSQL(session).listar()]


@router.post("/periodos/{periodo_id}/reabrir", response_model=schemas.PeriodoRespuesta)
def reabrir_periodo(periodo_id: UUID, session: Sesion):
    repo = RepositorioPeriodosSQL(session)
    periodo = repo.obtener(periodo_id)
    if periodo is None:
        raise HTTPException(404, "No existe el periodo")
    reabierto = periodo.con_estado(EstadoPeriodo.ABIERTO)  # cerrado ⇒ ValueError
    repo.guardar(reabierto)
    return traductores.periodo_a_schema(reabierto)


@router.get("/periodos/{periodo_id}/turnos", response_model=list[schemas.TurnoRespuesta])
def turnos_del_periodo(periodo_id: UUID, session: Sesion, unidad_id: UUID | None = None):
    """Grilla quincenal: turnos de todos los empleados (de la unidad) en el periodo."""
    periodo = RepositorioPeriodosSQL(session).obtener(periodo_id)
    if periodo is None:
        raise HTTPException(404, "No existe el periodo")
    turnos_repo = RepositorioTurnosSQL(session)
    resultado = []
    for empleado in RepositorioEmpleadosSQL(session).listar(unidad_id=unidad_id):
        registrados = turnos_repo.de_empleado_entre(
            empleado.id, periodo.fecha_inicio, periodo.fecha_fin
        )
        resultado.extend(traductores.turno_a_schema(t) for t in registrados)
    return resultado


# --- Turnos ---


@router.post("/turnos", response_model=schemas.TurnoRespuesta, status_code=201)
def registrar_turno(datos: schemas.TurnoCrear, session: Sesion):
    caso = RegistrarTurno(
        empleados=RepositorioEmpleadosSQL(session),
        periodos=RepositorioPeriodosSQL(session),
        turnos=RepositorioTurnosSQL(session),
    )
    registrado = caso.ejecutar(datos.empleado_id, datos.fecha, datos.hora_inicio, datos.hora_fin)
    return traductores.turno_a_schema(registrado)


@router.delete("/turnos/{turno_id}", status_code=204)
def eliminar_turno(turno_id: UUID, session: Sesion):
    if not RepositorioTurnosSQL(session).eliminar(turno_id):
        raise HTTPException(404, "No existe el turno")


# --- Parámetros legales (RF5) ---


@router.get("/parametros", response_model=list[schemas.ParametroRespuesta])
def listar_parametros(session: Sesion, fecha: date | None = None):
    """Historial completo, o solo los vigentes en `fecha`."""
    parametros = RepositorioParametrosSQL(session).listar()
    if fecha is not None:
        parametros = [p for p in parametros if p.vigencia.contiene(fecha)]
    return [
        schemas.ParametroRespuesta(
            codigo=p.codigo,
            valor=p.valor,
            vigente_desde=p.vigencia.desde,
            vigente_hasta=p.vigencia.hasta,
            norma=p.norma,
        )
        for p in parametros
    ]


@router.post("/parametros", response_model=schemas.ParametroRespuesta, status_code=201)
def crear_vigencia_parametro(datos: schemas.ParametroCrear, session: Sesion):
    caso = ActualizarParametro(parametros=RepositorioParametrosSQL(session))
    nuevo = caso.ejecutar(datos.codigo, datos.valor, datos.vigente_desde, datos.norma)
    return schemas.ParametroRespuesta(
        codigo=nuevo.codigo,
        valor=nuevo.valor,
        vigente_desde=nuevo.vigencia.desde,
        vigente_hasta=nuevo.vigencia.hasta,
        norma=nuevo.norma,
    )


# --- Festivos (RF4) ---


@router.get("/festivos/{anio}", response_model=list[schemas.FestivoRespuesta])
def festivos_del_anio(anio: int, session: Sesion):
    agregados, anulados = RepositorioFestivosSQL(session).ajustes()
    resultado = [
        schemas.FestivoRespuesta(fecha=f, nombre="", origen="ley")
        for f in festivos_por_ley(anio)
        if f not in anulados
    ]
    resultado += [
        schemas.FestivoRespuesta(fecha=f, nombre="", origen="manual")
        for f in agregados
        if f.year == anio
    ]
    return sorted(resultado, key=lambda f: f.fecha)


@router.put("/festivos", response_model=schemas.FestivoRespuesta)
def ajustar_festivo(datos: schemas.FestivoAjustar, session: Sesion):
    """Agrega un festivo manual, o anula uno calculado (es_festivo=false)."""
    RepositorioFestivosSQL(session).agregar_ajuste(datos.fecha, datos.nombre, datos.es_festivo)
    return schemas.FestivoRespuesta(fecha=datos.fecha, nombre=datos.nombre, origen="manual")


@router.delete("/festivos/{fecha}", status_code=204)
def quitar_ajuste_festivo(fecha: date, session: Sesion):
    if not RepositorioFestivosSQL(session).eliminar_ajuste(fecha):
        raise HTTPException(404, "No hay ajuste manual para esa fecha")


# --- Liquidación (RF3/RF6) ---


def _caso_liquidar(session: Session) -> LiquidarQuincena:
    return LiquidarQuincena(
        periodos=RepositorioPeriodosSQL(session),
        unidades=RepositorioUnidadesSQL(session),
        empleados=RepositorioEmpleadosSQL(session),
        turnos=RepositorioTurnosSQL(session),
        parametros=RepositorioParametrosSQL(session),
        festivos=RepositorioFestivosSQL(session),
        liquidaciones=RepositorioLiquidacionesSQL(session),
    )


@router.post(
    "/periodos/{periodo_id}/liquidar",
    response_model=schemas.LiquidacionRespuesta,
    status_code=201,
)
def liquidar_periodo(periodo_id: UUID, datos: schemas.LiquidarSolicitud, session: Sesion):
    liquidacion = _caso_liquidar(session).ejecutar(periodo_id, datos.unidad_id)
    return traductores.liquidacion_a_schema(liquidacion)


@router.get("/liquidaciones", response_model=list[schemas.LiquidacionRespuesta])
def listar_liquidaciones(session: Sesion, periodo_id: UUID | None = None):
    liquidaciones = RepositorioLiquidacionesSQL(session).listar(periodo_id=periodo_id)
    return [traductores.liquidacion_a_schema(liq) for liq in liquidaciones]


@router.get("/liquidaciones/{liquidacion_id}", response_model=schemas.LiquidacionRespuesta)
def obtener_liquidacion(liquidacion_id: UUID, session: Sesion):
    liquidacion = RepositorioLiquidacionesSQL(session).obtener(liquidacion_id)
    if liquidacion is None:
        raise HTTPException(404, "No existe la liquidación")
    return traductores.liquidacion_a_schema(liquidacion)


@router.get("/liquidaciones/{liquidacion_id}/excel")
def descargar_liquidacion_excel(liquidacion_id: UUID, session: Sesion) -> Response:
    caso = ExportarLiquidacion(
        liquidaciones=RepositorioLiquidacionesSQL(session),
        exportador=exportar_liquidacion_excel,
    )
    contenido, nombre = caso.ejecutar(liquidacion_id)
    return Response(
        content=contenido,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{nombre}"'},
    )
