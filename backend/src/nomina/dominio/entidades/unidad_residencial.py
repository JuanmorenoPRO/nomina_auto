from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from uuid import UUID

from nomina.dominio.entidades.concepto_liquidado import ConceptoManual


@dataclass(frozen=True)
class ConfiguracionUnidad:
    """Configuración de cálculo propia de una unidad.

    - `estrategia_extras`: sobreescribe la estrategia global de clasificación de
      extras (`presupuesto_quincenal` / `semanal_legal` / `diaria`). None = usar
      la estrategia global vigente.
    - `factores_override`: factor fijo por código de concepto que reemplaza el
      factor aditivo del motor (para unidades cuya planilla usa una tabla de
      factores legada, ej. combinados con el recargo dominical viejo).
    - `conceptos_fijos`: devengados/deducciones que se aplican AUTOMÁTICAMENTE a
      todos los empleados de la unidad en cada liquidación (ej. cuota de manejo).
    """

    estrategia_extras: str | None = None
    factores_override: dict[str, Decimal] = field(default_factory=dict)
    conceptos_fijos: tuple[ConceptoManual, ...] = ()


@dataclass(frozen=True)
class UnidadResidencial:
    id: UUID
    nombre: str
    nit: str = ""
    activa: bool = True
    descuenta_seguridad_social: bool = False
    config: ConfiguracionUnidad = field(default_factory=ConfiguracionUnidad)

    def __post_init__(self) -> None:
        if not self.nombre.strip():
            raise ValueError("La unidad residencial debe tener nombre")
