"""Datos de la unidad EDIFICIO PUEBLA P.H (quincena 1–15 jul 2026).

Unidad de referencia con DESCUENTO de seguridad social. Fuente: planilla real de
la contadora (`NOMINA PUEBLA JULIO.xlsx`). Los turnos están reconstruidos para que
la segmentación del motor + la estrategia `diaria` reproduzcan las HORAS por concepto
del documento. Ver [[unidad-puebla-descuento-ss]].

Notas de fidelidad (documentadas):
- Factores combinados: la planilla usa festivo diurno ×1.90 (recargo 90% nuevo) pero
  los combinados con el 0.75 viejo → `FACTORES_OVERRIDE` fija 2.0/2.1/2.5 por unidad.
- Nocturno dominical de Maria: el documento cuenta 2 h de domingo que cruzan a lunes
  como dominical; el motor las corta a medianoche (regla de negocio) → Maria queda con
  7 h de nocturno dominical (vs 9 del documento). Todo lo demás coincide al peso.
- La cuota de manejo ($7.095) es un devengado NO salarial. La planilla de Wilmar la
  incluyó por error en su IBC (~$284 de diferencia en salud/pensión).
"""

from __future__ import annotations

from datetime import date, time
from decimal import Decimal

from nomina.dominio.entidades.concepto_liquidado import DEVENGADO, ConceptoManual
from nomina.dominio.entidades.turno import Turno

NOMBRE_UNIDAD = "EDIFICIO PUEBLA P.H"
NIT = "811001922"
SALARIO_BASICO = Decimal("1750905")
PERIODO_INICIO = date(2026, 7, 1)
PERIODO_FIN = date(2026, 7, 15)
ESTRATEGIA_EXTRAS = "diaria"

# Factor fijo por concepto que usa la planilla (tabla de factores legada).
FACTORES_OVERRIDE: dict[str, Decimal] = {
    "extra_diurna_festiva": Decimal("2.0"),   # TIEMPO FESTIVO EXTRA
    "extra_nocturna_festiva": Decimal("2.5"),  # TIEMPO EXTRA NOCTURNO DOMINICAL/FESTIVO
    "festivo_nocturno": Decimal("2.1"),        # TIEMPO NOCTURNO DOMINICAL/FESTIVO
}

CUOTA_MANEJO = ConceptoManual(
    nombre="CUOTA DE MANEJO TARJETA", valor=Decimal("7095"), tipo=DEVENGADO, salarial=False
)

# (nombre, documento, cargo)
EMPLEADOS = [
    ("MARIA HERESBEY AGUIRRE", "43623487", "aseo"),
    ("WILMAR ALBERTO RIOS", "71726091", "vigilante"),
]

# Turnos por documento: (día del mes, hora_inicio HH, hora_fin HH). hora_fin 0 = medianoche.
# Reconstruidos para reproducir las horas por concepto del documento vía segmentación + `diaria`.
TURNOS: dict[str, list[tuple[int, int, int]]] = {
    "43623487": [  # MARIA
        (1, 16, 0), (2, 16, 0), (4, 6, 18), (5, 6, 18), (6, 16, 0), (7, 16, 0),
        (8, 16, 0), (9, 19, 0), (10, 6, 18), (12, 0, 7), (12, 19, 0), (14, 11, 23),
    ],
    "71726091": [  # WILMAR
        (1, 11, 23), (2, 11, 23), (3, 6, 18), (5, 6, 14), (6, 11, 23), (7, 21, 6),
        (8, 22, 6), (9, 22, 6), (10, 22, 6), (12, 0, 7), (12, 19, 0), (13, 22, 6),
        (14, 22, 6), (15, 21, 23),
    ],
}


def turnos_de(documento: str) -> list[Turno]:
    """Objetos Turno del empleado para la quincena 1–15 jul 2026."""
    return [
        Turno(
            fecha=date(2026, 7, dia),
            hora_inicio=time(hi % 24),
            hora_fin=time(hf % 24),
        )
        for dia, hi, hf in TURNOS[documento]
    ]
