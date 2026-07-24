from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from uuid import UUID

DEVENGADO = "devengado"
DEDUCCION = "deduccion"


@dataclass(frozen=True)
class ConceptoLiquidado:
    """Una línea de la liquidación: minutos × tarifa × factor = valor.

    `componentes` desglosa el factor (ej. {'hora_base': 1, 'recargo_dominical_festivo':
    0.80, 'recargo_nocturno': 0.35}) para que el reporte sea auditable.
    Los conceptos sin horas (ej. auxilio de transporte, deducciones) llevan
    minutos=0 y factor=None.
    """

    codigo: str
    nombre: str
    minutos: int
    valor: Decimal
    tarifa_hora: Decimal | None = None
    factor: Decimal | None = None
    componentes: dict[str, Decimal] = field(default_factory=dict)

    @property
    def horas(self) -> Decimal:
        return Decimal(self.minutos) / 60


@dataclass(frozen=True)
class ConceptoManual:
    """Concepto cargado a mano por empleado/periodo: un devengado adicional
    (ej. cuota de manejo de tarjeta) o una deducción (ej. préstamo).

    `salarial` solo aplica a los devengados: indica si suma al IBC de aportes.
    """

    nombre: str
    valor: Decimal
    tipo: str = DEVENGADO  # DEVENGADO | DEDUCCION
    salarial: bool = False


@dataclass(frozen=True)
class ConceptoManualRegistrado:
    """Concepto manual persistido: identidad + empleado + periodo + el concepto."""

    id: UUID
    empleado_id: UUID
    periodo_id: UUID
    concepto: ConceptoManual


@dataclass(frozen=True)
class Liquidacion:
    """Resultado de liquidar la quincena de un empleado. Conceptos ADICIONALES
    al salario base van desglosados; los totales suman valores ya redondeados.

    `conceptos` son los devengados; `deducciones` los descuentos (salud, pensión,
    otras). El neto a pagar = total devengado − total deducciones.
    """

    salario_mensual: Decimal
    tarifa_hora: Decimal
    conceptos: tuple[ConceptoLiquidado, ...]
    deducciones: tuple[ConceptoLiquidado, ...] = ()

    @property
    def total_devengado(self) -> Decimal:
        return sum((c.valor for c in self.conceptos), Decimal(0))

    @property
    def total_deducciones(self) -> Decimal:
        return sum((d.valor for d in self.deducciones), Decimal(0))

    @property
    def neto_a_pagar(self) -> Decimal:
        return self.total_devengado - self.total_deducciones

    @property
    def total(self) -> Decimal:
        """Alias histórico: total devengado (los conceptos ya redondeados)."""
        return self.total_devengado
