"""Datos de la quincena 16-31 jul 2026 de EDIFICIO RIO CLARO P.H.

Es la primera quincena del repo que cae en un mes de 31 días, el caso que
motivó el concepto `dia_31`: la planilla liquida SIEMPRE 15 días
(`DIAS LAB = 15` → 210/30 × 15 = 105 h de TIEMPO ORDINARIO), así que el 31 es un
16.º día que el salario no cubre y la contadora lo reconoce aparte, a hora base,
en una línea `DIA 31 TURNO DIA` / `DIA 31 TURNO NOCHE`.

Mismo enfoque que `julio_1_15.py` y `puebla.py`: los turnos están reconstruidos
—no son el horario real— para que la segmentación + la estrategia `jornada`
reproduzcan el TOTAL de horas por concepto, no el detalle día a día. El detalle
de esta planilla tampoco es reproducible con una sola estrategia: el mismo turno
de 11 h paga 3 h extra el día 16 y ninguna el 23, y el lunes 20 (festivo) reparte
horas entre "tiempo nocturno" y "nocturno dominical".

Las horas ordinarias diurnas (columna B de la planilla) no se fijan: no son un
concepto liquidado —el salario paga el presupuesto de 105 h caiga donde caiga—,
así que la reconstrucción solo apunta a los conceptos que sí se pagan.

Fuente: JULIO RIO CLARO 2026.xlsx, hojas `<empleado> 16-30`.
"""

from __future__ import annotations

from datetime import date, time
from decimal import Decimal

from nomina.dominio.entidades.concepto_liquidado import DEDUCCION, DEVENGADO, ConceptoManual
from nomina.dominio.entidades.turno import Turno

NOMBRE_UNIDAD = "EDIFICIO RIO CLARO P.H"
NIT = "800084755"

PERIODO_INICIO = date(2026, 7, 16)
PERIODO_FIN = date(2026, 7, 31)
SALARIO_BASICO = Decimal("1750905")

# Desde el 15-jul-2026 el par vigente es 105 h / divisor 210 → hora base 8.337,64.
ESTRATEGIA_EXTRAS = "jornada"
FACTORES_OVERRIDE: dict[str, Decimal] = {
    "extra_diurna_festiva": Decimal("2.0"),
    "extra_nocturna_festiva": Decimal("2.5"),
    "festivo_nocturno": Decimal("2.1"),
}

# Días especiales de la quincena: 19 y 26 son domingo; el 20 es festivo (20 de julio).

# --- Turnos reconstruidos por documento: (día, hora_inicio, hora_fin) ---------
# hora_fin puede pasarse de 24 (cruza medianoche) o traer .5 (media hora).

TURNOS: dict[str, list[tuple[int, float, float]]] = {
    # FREDY SEPULVEDA — nocturnos el 16 y el 31 (el del 31 cruza a agosto: es el
    # `DIA 31 TURNO NOCHE` de la planilla, 8 h no-extra).
    "15536952": [
        (16, 18, 29), (31, 18, 29),
        (19, 6, 13.5), (20, 6, 13.5), (26, 14, 21.5),
        (25, 14, 21.5), (27, 14, 21.5), (28, 14, 21.5),
        (29, 6, 18),
    ],
    # RIGOBERTO MARIN — no trabajó el 31.
    "71392880": [
        (16, 6, 17), (17, 6, 17), (22, 6, 17), (23, 6, 17),
        (24, 18, 29), (29, 18, 29), (30, 18, 29),
        (19, 6, 11), (20, 6, 11), (19, 19, 26.5), (26, 19, 24),
        (21, 19, 27), (22, 19, 27), (27, 19, 27), (28, 19, 22.5),
    ],
    # WALTER GOMEZ — turno de día el 31 (`DIA 31 TURNO DIA`, 8 h no-extra).
    "71878165": [
        (30, 6, 17), (31, 6, 17),
        (26, 6, 13.5), (19, 19, 26.5), (20, 19, 24), (26, 19, 21.5),
        (22, 19, 29), (23, 19, 29),
        (17, 19, 27), (21, 19, 27), (27, 19, 27), (28, 19, 20),
    ],
    # OLGA PIEDRAHITA — 8 h fijas de día; 88 h en la quincena, por debajo de las
    # 105 del presupuesto. La contadora NO le reconoció el 31 por eso mismo.
    "43581748": [
        (d, 7, 15) for d in (16, 17, 21, 22, 23, 24, 27, 28, 29, 30, 31)
    ],
}

# Empleados a los que la contadora les liquidó la línea del día 31.
PAGA_DIA_31 = frozenset({"15536952", "71878165"})

# --- Conceptos manuales por documento ----------------------------------------

CONCEPTOS_MANUALES: dict[str, tuple[ConceptoManual, ...]] = {
    "15536952": (  # FREDY
        ConceptoManual(nombre="RECONOCIMIENTO HORAS DIA 4 JULIO", valor=Decimal("28922"),
                       tipo=DEVENGADO, salarial=True),
    ),
    "71392880": (  # RIGOBERTO
        ConceptoManual(nombre="RECONOCIMIENTO HORAS DIA 4 JULIO", valor=Decimal("19403"),
                       tipo=DEVENGADO, salarial=True),
        ConceptoManual(nombre="DEDUCCION PRESTAMO", valor=Decimal("50000"), tipo=DEDUCCION),
    ),
    "71878165": (  # WALTER
        ConceptoManual(nombre="DEDUCCION DIA NO LABORADO CANCELADO (4 DE JULIO)",
                       valor=Decimal("73220"), tipo=DEDUCCION),
    ),
}


def turnos_de(documento: str) -> list[Turno]:
    """Objetos Turno del empleado para la quincena 16-31 jul 2026."""
    resultado = []
    for dia, hi, hf in TURNOS.get(documento, []):
        hi_h, hi_m = int(hi % 24), round((hi % 24 - int(hi % 24)) * 60)
        hf_h, hf_m = int(hf % 24), round((hf % 24 - int(hf % 24)) * 60)
        resultado.append(
            Turno(fecha=date(2026, 7, dia), hora_inicio=time(hi_h, hi_m), hora_fin=time(hf_h, hf_m))
        )
    return resultado
