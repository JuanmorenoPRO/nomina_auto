"""Schemas Pydantic: validación de entrada en TODOS los endpoints (RF/seguridad).

El dominio no conoce Pydantic; aquí solo se validan formas y rangos básicos.
Las reglas de negocio (solapamientos, periodos abiertos) viven en los casos de uso.
"""

from __future__ import annotations

from datetime import date, datetime, time
from uuid import UUID

from pydantic import BaseModel, Field, field_validator


class ConceptoFijoConfig(BaseModel):
    nombre: str = Field(min_length=1, max_length=100)
    valor: int = Field(gt=0, description="pesos enteros")
    tipo: str = Field(default="devengado", pattern="^(devengado|deduccion)$")
    salarial: bool = False


class UnidadConfig(BaseModel):
    estrategia_extras: str | None = None
    # factor fijo por código de concepto (texto decimal exacto, ej. {"festivo_nocturno": "2.1"})
    factores_override: dict[str, str] = Field(default_factory=dict)
    # devengados/deducciones fijos que se aplican a todos los empleados de la unidad
    conceptos_fijos: list[ConceptoFijoConfig] = Field(default_factory=list)


class UnidadCrear(BaseModel):
    nombre: str = Field(min_length=1, max_length=200)
    nit: str = Field(default="", max_length=30)
    descuenta_seguridad_social: bool = False
    config: UnidadConfig = Field(default_factory=UnidadConfig)


class UnidadActualizar(BaseModel):
    nombre: str | None = Field(default=None, min_length=1, max_length=200)
    nit: str | None = Field(default=None, max_length=30)
    activa: bool | None = None
    descuenta_seguridad_social: bool | None = None
    config: UnidadConfig | None = None


class UnidadRespuesta(BaseModel):
    id: UUID
    nombre: str
    nit: str
    activa: bool
    descuenta_seguridad_social: bool
    config: UnidadConfig


class EmpleadoCrear(BaseModel):
    unidad_id: UUID
    nombre: str = Field(min_length=1, max_length=200)
    tipo_documento: str = Field(default="CC", max_length=5)
    documento: str = Field(min_length=3, max_length=20)
    cargo: str = Field(min_length=1, max_length=100)
    salario_base: int = Field(gt=0, description="pesos enteros mensuales")

    @field_validator("documento")
    @classmethod
    def documento_numerico(cls, v: str) -> str:
        if not v.strip().isdigit():
            raise ValueError("El documento debe ser numérico")
        return v.strip()


class EmpleadoRespuesta(BaseModel):
    id: UUID
    unidad_id: UUID
    nombre: str
    tipo_documento: str
    documento: str
    cargo: str
    salario_base: int
    activo: bool


class ConceptoManualCrear(BaseModel):
    empleado_id: UUID
    periodo_id: UUID
    tipo: str = Field(default="devengado", pattern="^(devengado|deduccion)$")
    nombre: str = Field(min_length=1, max_length=100)
    valor: int = Field(gt=0, description="pesos enteros")
    salarial: bool = False


class ConceptoManualRespuesta(BaseModel):
    id: UUID
    empleado_id: UUID
    periodo_id: UUID
    tipo: str
    nombre: str
    valor: int
    salarial: bool


class PeriodoCrear(BaseModel):
    fecha_inicio: date
    fecha_fin: date

    @field_validator("fecha_fin")
    @classmethod
    def fin_no_antes_de_inicio(cls, v: date, info) -> date:
        inicio = info.data.get("fecha_inicio")
        if inicio and v < inicio:
            raise ValueError("fecha_fin no puede ser anterior a fecha_inicio")
        return v


class PeriodoRespuesta(BaseModel):
    id: UUID
    fecha_inicio: date
    fecha_fin: date
    estado: str


class TurnoCrear(BaseModel):
    empleado_id: UUID
    fecha: date
    hora_inicio: time
    hora_fin: time  # hora_fin <= hora_inicio ⇒ el turno cruza medianoche


class TurnoRespuesta(BaseModel):
    id: UUID
    empleado_id: UUID
    fecha: date
    hora_inicio: time
    hora_fin: time
    cruza_medianoche: bool


class ParametroCrear(BaseModel):
    codigo: str = Field(max_length=50)
    valor: str = Field(min_length=1, max_length=50)
    vigente_desde: date
    norma: str = Field(default="", max_length=200)


class ParametroRespuesta(BaseModel):
    codigo: str
    valor: str
    vigente_desde: date
    vigente_hasta: date | None
    norma: str


class FestivoAjustar(BaseModel):
    fecha: date
    nombre: str = Field(default="", max_length=100)
    es_festivo: bool = True  # False anula un festivo calculado por ley


class FestivoRespuesta(BaseModel):
    fecha: date
    nombre: str
    origen: str  # 'ley' | 'manual'


class LiquidarSolicitud(BaseModel):
    unidad_id: UUID


class ConceptoRespuesta(BaseModel):
    codigo: str
    nombre: str
    minutos: int
    horas: str  # decimal exacto como texto, ej. "11.50"
    factor: str | None
    componentes: dict[str, str]
    valor: int


class LiquidacionEmpleadoRespuesta(BaseModel):
    empleado_id: UUID
    nombre: str
    documento: str
    salario_mensual: int
    tarifa_hora: str
    conceptos: list[ConceptoRespuesta]
    deducciones: list[ConceptoRespuesta]
    total_devengado: int
    total_deducciones: int
    neto_a_pagar: int
    total: int  # alias histórico = total_devengado


class LiquidacionRespuesta(BaseModel):
    id: UUID
    periodo: PeriodoRespuesta
    unidad: UnidadRespuesta
    version: int
    creada_en: datetime
    empleados: list[LiquidacionEmpleadoRespuesta]
    total: int
