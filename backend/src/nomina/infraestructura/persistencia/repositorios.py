"""Implementaciones SQLAlchemy de los puertos de persistencia.

Traducen entre entidades de dominio (Decimal, dataclasses) y modelos ORM
(pesos enteros, texto exacto para decimales).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from nomina.aplicacion.casos_uso.liquidar_quincena import (
    LiquidacionEmpleado,
    LiquidacionQuincena,
)
from nomina.dominio.entidades.concepto_liquidado import ConceptoLiquidado, Liquidacion
from nomina.dominio.entidades.empleado import Empleado
from nomina.dominio.entidades.parametro_legal import ParametroLegal
from nomina.dominio.entidades.periodo_liquidacion import EstadoPeriodo, PeriodoLiquidacion
from nomina.dominio.entidades.turno import Turno, TurnoRegistrado
from nomina.dominio.entidades.unidad_residencial import UnidadResidencial
from nomina.dominio.valores.vigencia import Vigencia
from nomina.infraestructura.persistencia.modelos import (
    ConceptoLiquidadoModel,
    EmpleadoModel,
    FestivoModel,
    LiquidacionEmpleadoModel,
    LiquidacionModel,
    ParametroLegalModel,
    PeriodoLiquidacionModel,
    TurnoModel,
    UnidadResidencialModel,
)


@dataclass
class RepositorioUnidadesSQL:
    session: Session

    def guardar(self, unidad: UnidadResidencial) -> None:
        self.session.merge(
            UnidadResidencialModel(
                id=unidad.id, nombre=unidad.nombre, nit=unidad.nit, activa=unidad.activa
            )
        )
        self.session.flush()

    def obtener(self, id: UUID) -> UnidadResidencial | None:
        m = self.session.get(UnidadResidencialModel, id)
        return self._a_dominio(m) if m else None

    def listar(self) -> list[UnidadResidencial]:
        filas = self.session.scalars(
            select(UnidadResidencialModel).order_by(UnidadResidencialModel.nombre)
        )
        return [self._a_dominio(m) for m in filas]

    @staticmethod
    def _a_dominio(m: UnidadResidencialModel) -> UnidadResidencial:
        return UnidadResidencial(id=m.id, nombre=m.nombre, nit=m.nit, activa=m.activa)


@dataclass
class RepositorioEmpleadosSQL:
    session: Session

    def guardar(self, empleado: Empleado) -> None:
        self.session.merge(
            EmpleadoModel(
                id=empleado.id,
                unidad_id=empleado.unidad_id,
                nombre=empleado.nombre,
                tipo_documento=empleado.tipo_documento,
                documento=empleado.documento,
                cargo=empleado.cargo,
                salario_base=int(empleado.salario_base),
                activo=empleado.activo,
            )
        )
        self.session.flush()

    def obtener(self, id: UUID) -> Empleado | None:
        m = self.session.get(EmpleadoModel, id)
        return self._a_dominio(m) if m else None

    def listar(self, unidad_id: UUID | None = None, solo_activos: bool = False) -> list[Empleado]:
        consulta = select(EmpleadoModel).order_by(EmpleadoModel.nombre)
        if unidad_id is not None:
            consulta = consulta.where(EmpleadoModel.unidad_id == unidad_id)
        if solo_activos:
            consulta = consulta.where(EmpleadoModel.activo)
        return [self._a_dominio(m) for m in self.session.scalars(consulta)]

    @staticmethod
    def _a_dominio(m: EmpleadoModel) -> Empleado:
        return Empleado(
            id=m.id,
            unidad_id=m.unidad_id,
            nombre=m.nombre,
            tipo_documento=m.tipo_documento,
            documento=m.documento,
            cargo=m.cargo,
            salario_base=Decimal(m.salario_base),
            activo=m.activo,
        )


@dataclass
class RepositorioPeriodosSQL:
    session: Session

    def guardar(self, periodo: PeriodoLiquidacion) -> None:
        self.session.merge(
            PeriodoLiquidacionModel(
                id=periodo.id,
                fecha_inicio=periodo.fecha_inicio,
                fecha_fin=periodo.fecha_fin,
                estado=periodo.estado.value,
            )
        )
        self.session.flush()

    def obtener(self, id: UUID) -> PeriodoLiquidacion | None:
        m = self.session.get(PeriodoLiquidacionModel, id)
        return self._a_dominio(m) if m else None

    def listar(self) -> list[PeriodoLiquidacion]:
        filas = self.session.scalars(
            select(PeriodoLiquidacionModel).order_by(PeriodoLiquidacionModel.fecha_inicio.desc())
        )
        return [self._a_dominio(m) for m in filas]

    def que_contiene(self, fecha: date) -> PeriodoLiquidacion | None:
        m = self.session.scalars(
            select(PeriodoLiquidacionModel)
            .where(PeriodoLiquidacionModel.fecha_inicio <= fecha)
            .where(PeriodoLiquidacionModel.fecha_fin >= fecha)
        ).first()
        return self._a_dominio(m) if m else None

    @staticmethod
    def _a_dominio(m: PeriodoLiquidacionModel) -> PeriodoLiquidacion:
        return PeriodoLiquidacion(
            id=m.id,
            fecha_inicio=m.fecha_inicio,
            fecha_fin=m.fecha_fin,
            estado=EstadoPeriodo(m.estado),
        )


@dataclass
class RepositorioTurnosSQL:
    session: Session

    def guardar(self, turno: TurnoRegistrado) -> None:
        self.session.merge(
            TurnoModel(
                id=turno.id,
                empleado_id=turno.empleado_id,
                fecha=turno.turno.fecha,
                hora_inicio=turno.turno.hora_inicio,
                hora_fin=turno.turno.hora_fin,
            )
        )
        self.session.flush()

    def obtener(self, id: UUID) -> TurnoRegistrado | None:
        m = self.session.get(TurnoModel, id)
        if m is None:
            return None
        return TurnoRegistrado(
            id=m.id,
            empleado_id=m.empleado_id,
            turno=Turno(fecha=m.fecha, hora_inicio=m.hora_inicio, hora_fin=m.hora_fin),
        )

    def eliminar(self, id: UUID) -> bool:
        m = self.session.get(TurnoModel, id)
        if m is None:
            return False
        self.session.delete(m)
        self.session.flush()
        return True

    def de_empleado_entre(self, empleado_id: UUID, desde: date, hasta: date) -> list[TurnoRegistrado]:
        filas = self.session.scalars(
            select(TurnoModel)
            .where(TurnoModel.empleado_id == empleado_id)
            .where(TurnoModel.fecha >= desde)
            .where(TurnoModel.fecha <= hasta)
            .order_by(TurnoModel.fecha, TurnoModel.hora_inicio)
        )
        return [
            TurnoRegistrado(
                id=m.id,
                empleado_id=m.empleado_id,
                turno=Turno(fecha=m.fecha, hora_inicio=m.hora_inicio, hora_fin=m.hora_fin),
            )
            for m in filas
        ]


@dataclass
class RepositorioParametrosSQL:
    session: Session

    def listar(self) -> list[ParametroLegal]:
        filas = self.session.scalars(
            select(ParametroLegalModel).order_by(
                ParametroLegalModel.codigo, ParametroLegalModel.vigente_desde
            )
        )
        return [
            ParametroLegal(
                codigo=m.codigo,
                valor=m.valor,
                vigencia=Vigencia(desde=m.vigente_desde, hasta=m.vigente_hasta),
                norma=m.norma,
            )
            for m in filas
        ]

    def agregar(self, parametro: ParametroLegal) -> None:
        self.session.add(
            ParametroLegalModel(
                codigo=parametro.codigo,
                valor=parametro.valor,
                vigente_desde=parametro.vigencia.desde,
                vigente_hasta=parametro.vigencia.hasta,
                norma=parametro.norma,
            )
        )
        self.session.flush()

    def cerrar_vigencia_abierta(self, codigo: str, hasta: date) -> None:
        abierta = self.session.scalars(
            select(ParametroLegalModel)
            .where(ParametroLegalModel.codigo == codigo)
            .where(ParametroLegalModel.vigente_hasta.is_(None))
        ).first()
        if abierta is not None:
            abierta.vigente_hasta = hasta
            self.session.flush()


@dataclass
class RepositorioFestivosSQL:
    session: Session

    def agregar_ajuste(self, fecha: date, nombre: str, es_festivo: bool) -> None:
        existente = self.session.scalars(
            select(FestivoModel).where(FestivoModel.fecha == fecha)
        ).first()
        if existente is not None:
            existente.nombre, existente.es_festivo = nombre, es_festivo
        else:
            self.session.add(FestivoModel(fecha=fecha, nombre=nombre, es_festivo=es_festivo))
        self.session.flush()

    def eliminar_ajuste(self, fecha: date) -> bool:
        m = self.session.scalars(select(FestivoModel).where(FestivoModel.fecha == fecha)).first()
        if m is None:
            return False
        self.session.delete(m)
        self.session.flush()
        return True

    def ajustes(self) -> tuple[frozenset[date], frozenset[date]]:
        filas = list(self.session.scalars(select(FestivoModel)))
        agregados = frozenset(m.fecha for m in filas if m.es_festivo)
        anulados = frozenset(m.fecha for m in filas if not m.es_festivo)
        return agregados, anulados


@dataclass
class RepositorioLiquidacionesSQL:
    session: Session

    def guardar(self, liquidacion: LiquidacionQuincena, parametros_snapshot: list[dict]) -> None:
        modelo = LiquidacionModel(
            id=liquidacion.id,
            periodo_id=liquidacion.periodo.id,
            unidad_id=liquidacion.unidad.id,
            version=liquidacion.version,
            parametros_snapshot=parametros_snapshot,
            creada_en=liquidacion.creada_en,
        )
        for le in liquidacion.por_empleado:
            emp_modelo = LiquidacionEmpleadoModel(
                empleado_id=le.empleado.id,
                nombre_empleado=le.empleado.nombre,
                salario_mensual=int(le.liquidacion.salario_mensual),
                tarifa_hora=str(le.liquidacion.tarifa_hora),
            )
            for orden, c in enumerate(le.liquidacion.conceptos):
                emp_modelo.conceptos.append(
                    ConceptoLiquidadoModel(
                        orden=orden,
                        codigo=c.codigo,
                        nombre=c.nombre,
                        minutos=c.minutos,
                        tarifa_hora=str(c.tarifa_hora) if c.tarifa_hora is not None else None,
                        factor=str(c.factor) if c.factor is not None else None,
                        componentes={k: str(v) for k, v in c.componentes.items()},
                        valor=int(c.valor),
                    )
                )
            modelo.empleados.append(emp_modelo)
        self.session.add(modelo)
        self.session.flush()

    def obtener(self, id: UUID) -> LiquidacionQuincena | None:
        m = self.session.get(LiquidacionModel, id)
        return self._a_dominio(m) if m else None

    def listar(self, periodo_id: UUID | None = None) -> list[LiquidacionQuincena]:
        consulta = select(LiquidacionModel).order_by(LiquidacionModel.creada_en.desc())
        if periodo_id is not None:
            consulta = consulta.where(LiquidacionModel.periodo_id == periodo_id)
        return [self._a_dominio(m) for m in self.session.scalars(consulta)]

    def ultima_version(self, periodo_id: UUID, unidad_id: UUID) -> int:
        versiones = self.session.scalars(
            select(LiquidacionModel.version)
            .where(LiquidacionModel.periodo_id == periodo_id)
            .where(LiquidacionModel.unidad_id == unidad_id)
        ).all()
        return max(versiones, default=0)

    def _a_dominio(self, m: LiquidacionModel) -> LiquidacionQuincena:
        periodo = RepositorioPeriodosSQL(self.session).obtener(m.periodo_id)
        unidad = RepositorioUnidadesSQL(self.session).obtener(m.unidad_id)
        empleados_repo = RepositorioEmpleadosSQL(self.session)
        assert periodo is not None and unidad is not None
        por_empleado = []
        for le in m.empleados:
            empleado = empleados_repo.obtener(le.empleado_id)
            assert empleado is not None
            conceptos = tuple(
                ConceptoLiquidado(
                    codigo=c.codigo,
                    nombre=c.nombre,
                    minutos=c.minutos,
                    tarifa_hora=Decimal(c.tarifa_hora) if c.tarifa_hora else None,
                    factor=Decimal(c.factor) if c.factor else None,
                    componentes={k: Decimal(v) for k, v in c.componentes.items()},
                    valor=Decimal(c.valor),
                )
                for c in le.conceptos
            )
            por_empleado.append(
                LiquidacionEmpleado(
                    empleado=empleado,
                    liquidacion=Liquidacion(
                        salario_mensual=Decimal(le.salario_mensual),
                        tarifa_hora=Decimal(le.tarifa_hora),
                        conceptos=conceptos,
                    ),
                )
            )
        return LiquidacionQuincena(
            id=m.id,
            periodo=periodo,
            unidad=unidad,
            version=m.version,
            creada_en=m.creada_en,
            por_empleado=tuple(por_empleado),
        )
