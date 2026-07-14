"""Modelos SQLAlchemy. Convenciones:

- PK UUID (no secuenciales expuestos).
- Dinero en pesos ENTEROS (BigInteger); tarifas y factores como texto exacto
  (snapshot de Decimal) — nunca float, ni siquiera en SQLite.
- Fechas/horas de negocio en hora local Bogotá; timestamps técnicos en UTC.
"""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime, time

from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Time,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from nomina.infraestructura.persistencia.base import Base


def _ahora_utc() -> datetime:
    return datetime.now(UTC)


class UnidadResidencialModel(Base):
    __tablename__ = "unidad_residencial"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    nombre: Mapped[str] = mapped_column(String(200), unique=True)
    nit: Mapped[str] = mapped_column(String(30), default="")
    activa: Mapped[bool] = mapped_column(Boolean, default=True)


class EmpleadoModel(Base):
    __tablename__ = "empleado"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    unidad_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("unidad_residencial.id"))
    nombre: Mapped[str] = mapped_column(String(200))
    tipo_documento: Mapped[str] = mapped_column(String(5), default="CC")
    documento: Mapped[str] = mapped_column(String(20), unique=True)
    cargo: Mapped[str] = mapped_column(String(100))
    salario_base: Mapped[int] = mapped_column(BigInteger)  # pesos enteros
    activo: Mapped[bool] = mapped_column(Boolean, default=True)


class PeriodoLiquidacionModel(Base):
    __tablename__ = "periodo_liquidacion"
    __table_args__ = (UniqueConstraint("fecha_inicio", "fecha_fin"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    fecha_inicio: Mapped[date] = mapped_column(Date)
    fecha_fin: Mapped[date] = mapped_column(Date)
    estado: Mapped[str] = mapped_column(String(10), default="abierto")


class TurnoModel(Base):
    __tablename__ = "turno"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    empleado_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("empleado.id"), index=True)
    fecha: Mapped[date] = mapped_column(Date, index=True)  # día en que INICIA
    hora_inicio: Mapped[time] = mapped_column(Time)
    hora_fin: Mapped[time] = mapped_column(Time)  # <= inicio ⇒ cruza medianoche


class ParametroLegalModel(Base):
    __tablename__ = "parametro_legal"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    codigo: Mapped[str] = mapped_column(String(50), index=True)
    valor: Mapped[str] = mapped_column(String(50))
    vigente_desde: Mapped[date] = mapped_column(Date)
    vigente_hasta: Mapped[date | None] = mapped_column(Date, nullable=True)
    norma: Mapped[str] = mapped_column(String(200), default="")


class FestivoModel(Base):
    __tablename__ = "festivo"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    fecha: Mapped[date] = mapped_column(Date, unique=True)
    nombre: Mapped[str] = mapped_column(String(100), default="")
    # True: festivo manual adicional; False: anula un festivo calculado por ley
    es_festivo: Mapped[bool] = mapped_column(Boolean, default=True)


class LiquidacionModel(Base):
    __tablename__ = "liquidacion"
    __table_args__ = (UniqueConstraint("periodo_id", "unidad_id", "version"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    periodo_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("periodo_liquidacion.id"))
    unidad_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("unidad_residencial.id"))
    version: Mapped[int] = mapped_column(Integer)
    # snapshot de TODOS los parámetros al liquidar: reproducibilidad histórica
    parametros_snapshot: Mapped[list] = mapped_column(JSON, default=list)
    creada_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_ahora_utc)

    empleados: Mapped[list[LiquidacionEmpleadoModel]] = relationship(
        back_populates="liquidacion", cascade="all, delete-orphan", order_by="LiquidacionEmpleadoModel.nombre_empleado"
    )


class LiquidacionEmpleadoModel(Base):
    """Snapshot por empleado: nombre y salario al momento de liquidar."""

    __tablename__ = "liquidacion_empleado"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    liquidacion_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("liquidacion.id"), index=True)
    empleado_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("empleado.id"))
    nombre_empleado: Mapped[str] = mapped_column(String(200))
    salario_mensual: Mapped[int] = mapped_column(BigInteger)
    tarifa_hora: Mapped[str] = mapped_column(String(30))  # Decimal exacto como texto

    liquidacion: Mapped[LiquidacionModel] = relationship(back_populates="empleados")
    conceptos: Mapped[list[ConceptoLiquidadoModel]] = relationship(
        back_populates="liquidacion_empleado", cascade="all, delete-orphan",
        order_by="ConceptoLiquidadoModel.orden",
    )


class UsuarioModel(Base):
    __tablename__ = "usuario"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(String(200), unique=True)
    hash_password: Mapped[str] = mapped_column(String(255))  # Argon2id
    rol: Mapped[str] = mapped_column(String(10))
    activo: Mapped[bool] = mapped_column(Boolean, default=True)


class SesionModel(Base):
    """Sesiones con expiración. Se guarda el SHA-256 del token, nunca el token."""

    __tablename__ = "sesion"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    usuario_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("usuario.id"), index=True)
    expira_en: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    creada_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_ahora_utc)


class AuditoriaModel(Base):
    """Registro append-only (RF7): triggers de BD bloquean UPDATE y DELETE."""

    __tablename__ = "auditoria"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    usuario_email: Mapped[str] = mapped_column(String(200))
    accion: Mapped[str] = mapped_column(String(40))
    entidad: Mapped[str] = mapped_column(String(40))
    entidad_id: Mapped[str] = mapped_column(String(40), default="")
    antes: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    despues: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_ahora_utc)


class ConceptoLiquidadoModel(Base):
    __tablename__ = "concepto_liquidado"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    liquidacion_empleado_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("liquidacion_empleado.id"), index=True
    )
    orden: Mapped[int] = mapped_column(Integer, default=0)
    codigo: Mapped[str] = mapped_column(String(50))
    nombre: Mapped[str] = mapped_column(String(100))
    minutos: Mapped[int] = mapped_column(Integer)
    tarifa_hora: Mapped[str | None] = mapped_column(String(30), nullable=True)
    factor: Mapped[str | None] = mapped_column(String(15), nullable=True)
    componentes: Mapped[dict] = mapped_column(JSON, default=dict)
    valor: Mapped[int] = mapped_column(BigInteger)  # pesos enteros

    liquidacion_empleado: Mapped[LiquidacionEmpleadoModel] = relationship(
        back_populates="conceptos"
    )
