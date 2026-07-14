from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal


@dataclass(frozen=True)
class ConceptoLiquidado:
    """Una línea de la liquidación: minutos × tarifa × factor = valor.

    `componentes` desglosa el factor (ej. {'hora_base': 1, 'recargo_dominical_festivo':
    0.80, 'recargo_nocturno': 0.35}) para que el reporte sea auditable.
    Los conceptos sin horas (ej. auxilio de transporte) llevan minutos=0 y factor=None.
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
class Liquidacion:
    """Resultado de liquidar la quincena de un empleado. Conceptos ADICIONALES
    al salario base van desglosados; el total es la suma de valores ya redondeados."""

    salario_mensual: Decimal
    tarifa_hora: Decimal
    conceptos: tuple[ConceptoLiquidado, ...]

    @property
    def total(self) -> Decimal:
        return sum((c.valor for c in self.conceptos), Decimal(0))
