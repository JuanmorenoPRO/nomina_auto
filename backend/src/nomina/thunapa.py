"""Datos de la unidad EDIFICIO THUNAPA P.H (mayo 2026, dos quincenas).

Thunapa es la unidad "de referencia" que calibró originalmente el modelo de pago
aditivo (`docs/arquitectura.md` §5.3, `divisor_hora_ordinaria=220`, salario
mínimo 1.750.905) a partir de `NOMINA MAYO THUNAPA.xlsx`, pero nunca se había
persistido como datos reales: la unidad existía en Railway como una fila vacía
(sin empleados, sin turnos, sin `config`). Este módulo reconstruye ambas
quincenas de mayo 2026 (1-15 y 16-31) para 4 empleados, igual que `puebla.py`.

Los turnos NO son el horario real: están reconstruidos para que la
segmentación del motor + la estrategia `jornada` reproduzcan el TOTAL de horas
por concepto de cada hoja del Excel (mismo enfoque que `puebla.py` y
`julio_1_15.py`). Verificado con un harness de segmentar+clasificar+liquidar
hasta calzar exacto en las 8 combinaciones (4 empleados × 2 quincenas) — ver
golden test `tests/dominio/golden/test_golden_thunapa.py`.

Notas de fidelidad (documentadas):
- Misma tabla de factores legada que Puebla/julio_1_15: festivo diurno usa el
  recargo vigente (80%), pero los combinados (festivo-extra, nocturno-dominical,
  extra-nocturna-festiva) usan la tabla vieja 2.0/2.1/2.5 → `FACTORES_OVERRIDE`.
- `descuenta_seguridad_social=False`: las 8 hojas del Excel muestran SALUD y
  PENSIÓN en 0.
- FREDY tiene una `DEDUCCION PRESTAMO` de $50.000 en AMBAS quincenas (aparece
  igual en las hojas "FREDY 1-15" y "FREDY 16-30").
- `TIEMPO ORDINARIO` (110h) y `AUXILIO DE TRANSPORTE` son fijos/automáticos del
  motor (`horas_quincena`/`auxilio_transporte_mensual`) — no dependen de los
  turnos reconstruidos, así que no son objetivo de la reconstrucción.
- Los totales calzan al peso salvo una diferencia sistemática de 1-2 pesos por
  quincena: el motor redondea cada concepto por separado (`ROUND_HALF_UP`,
  regla del repo — ver CLAUDE.md), mientras que el total del Excel es la suma
  de valores SIN redondear y luego se redondea una sola vez. Mismo patrón
  documentado en `puebla.py`/`test_golden_puebla.py`.
"""

from __future__ import annotations

from datetime import date, time
from decimal import Decimal

from nomina.dominio.entidades.concepto_liquidado import DEDUCCION, ConceptoManual
from nomina.dominio.entidades.turno import Turno

NOMBRE_UNIDAD = "EDIFICIO THUNAPA P.H"
NIT = "800254433"
SALARIO_BASICO = Decimal("1750905")

PERIODO_1_INICIO = date(2026, 5, 1)
PERIODO_1_FIN = date(2026, 5, 15)
PERIODO_2_INICIO = date(2026, 5, 16)
PERIODO_2_FIN = date(2026, 5, 31)

# Extras por turno/jornada continua (igual que Puebla y las 7 unidades de julio).
ESTRATEGIA_EXTRAS = "jornada"

# Factor fijo por concepto que usa la planilla (tabla de factores legada, igual
# que Puebla — confirmado contra esta misma familia de planillas en §5.3).
FACTORES_OVERRIDE: dict[str, Decimal] = {
    "extra_diurna_festiva": Decimal("2.0"),
    "extra_nocturna_festiva": Decimal("2.5"),
    "festivo_nocturno": Decimal("2.1"),
}

# (nombre, documento, cargo)
EMPLEADOS = [
    ("FREDY ALONSO HURTADO", "71712119", "vigilante"),
    ("HECTOR EMILIO GALLEGO CASTAÑO", "70323354", "vigilante"),
    ("JUAN PABLO ESPINAL", "15264412", "vigilante"),
    ("JOHAN LOPEZ SANDOVAL", "1000569123", "vigilante"),
]

# --- Turnos reconstruidos por documento: (día del mes, hora_inicio, hora_fin) --
# hora_fin puede pasarse de 24 (cruza medianoche). Mismo formato que puebla.py.

TURNOS_1_15: dict[str, list[tuple[int, float, float]]] = {
    "71712119": [  # FREDY
        (1, 6, 18), (3, 7, 12), (2, 19, 30), (9, 20, 29),
        (4, 19, 30), (5, 19, 30), (6, 19, 30), (7, 19, 28), (8, 19, 27), (11, 19, 26),
        (12, 6, 18), (13, 6, 18), (14, 6, 18), (15, 6, 16),
    ],
    "70323354": [  # HECTOR
        (2, 6, 18), (4, 6, 18), (5, 6, 18), (6, 6, 18), (7, 6, 18),
        (8, 6, 18), (9, 6, 18), (11, 6, 18), (12, 6, 18), (13, 6, 18),
    ],
    "15264412": [  # JUAN PABLO
        (1, 6, 14), (3, 7, 13), (3, 0, 6), (10, 0, 2),
        (4, 19, 30), (6, 19, 22), (7, 11, 20),
        (2, 6, 18), (8, 6, 18), (9, 6, 18), (11, 6, 18),
    ],
    "1000569123": [  # JOHAN LOPEZ
        (1, 6, 14), (3, 0, 6), (10, 0, 1),
        (4, 19, 30), (6, 19, 30), (8, 19, 30), (11, 19, 30), (13, 19, 27),
        (2, 19, 20), (15, 19, 24),
        (2, 6, 18), (15, 6, 18),
    ],
}

TURNOS_16_31: dict[str, list[tuple[int, float, float]]] = {
    "71712119": [  # FREDY
        (17, 7, 15), (18, 6, 14), (24, 6, 11),
        (16, 19, 30), (23, 20, 29), (19, 19, 27), (20, 19, 22),
        (21, 6, 18), (22, 6, 18), (25, 6, 18), (26, 6, 18), (27, 6, 18), (28, 6, 18),
    ],
    "70323354": [  # HECTOR
        (16, 6, 18), (19, 6, 18), (20, 6, 18), (21, 6, 18), (22, 6, 18),
        (23, 6, 18), (25, 6, 18), (26, 6, 18), (27, 6, 18), (28, 6, 18),
    ],
    "15264412": [  # JUAN PABLO
        (17, 7, 12), (18, 6, 14), (17, 0, 6), (24, 0, 6), (18, 0, 3), (30, 11, 28),
        (19, 19, 30), (21, 19, 30), (25, 19, 27), (27, 19, 27), (29, 19, 25),
        (20, 7, 19), (22, 7, 19), (23, 6, 18), (26, 6, 18), (28, 6, 17),
    ],
    "1000569123": [  # JOHAN LOPEZ
        (17, 7, 15), (18, 6, 14), (24, 6, 8), (17, 0, 6), (18, 0, 4),
        (23, 13, 28),
        (19, 19, 30), (21, 19, 30), (25, 19, 30), (27, 19, 30), (29, 19, 30),
        (16, 19, 23), (20, 19, 21),
        (16, 6, 18), (22, 7, 19),
    ],
}

_PRESTAMO_FREDY = ConceptoManual(nombre="DEDUCCION PRESTAMO", valor=Decimal("50000"), tipo=DEDUCCION)

CONCEPTOS_MANUALES_1_15: dict[str, tuple[ConceptoManual, ...]] = {
    "71712119": (_PRESTAMO_FREDY,),
}
CONCEPTOS_MANUALES_16_31: dict[str, tuple[ConceptoManual, ...]] = {
    "71712119": (_PRESTAMO_FREDY,),
}


def _turnos_de(mes: int, tuplas: list[tuple[int, float, float]]) -> list[Turno]:
    resultado = []
    for dia, hi, hf in tuplas:
        hi_h, hi_m = int(hi % 24), round((hi % 24 - int(hi % 24)) * 60)
        hf_h, hf_m = int(hf % 24), round((hf % 24 - int(hf % 24)) * 60)
        resultado.append(
            Turno(fecha=date(2026, mes, dia), hora_inicio=time(hi_h, hi_m), hora_fin=time(hf_h, hf_m))
        )
    return resultado


def turnos_1_15_de(documento: str) -> list[Turno]:
    """Turnos del empleado para la quincena 1-15 mayo 2026."""
    return _turnos_de(5, TURNOS_1_15.get(documento, []))


def turnos_16_31_de(documento: str) -> list[Turno]:
    """Turnos del empleado para la quincena 16-31 mayo 2026."""
    return _turnos_de(5, TURNOS_16_31.get(documento, []))
