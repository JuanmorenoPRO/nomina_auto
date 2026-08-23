"""Datos de DEMOSTRACIÓN — unidades, empleados y turnos ficticios.

A diferencia de `puebla.py`, `thunapa.py` y `julio_1_15.py` —que reconstruyen
planillas reales de la contadora y sirven de referencia para los golden tests—
este módulo NO reproduce ninguna nómina real: los nombres, las cédulas y los
horarios son inventados. Existe para dos cosas:

1. Levantar la aplicación con datos de ejemplo sin tocar la base de trabajo
   (ver `sembrar_demo.py`).
2. Generar las capturas de `docs/manual-usuario.md` sin exponer datos personales
   de empleados reales (Ley 1581/2012).

La quincena es el **1 al 15 de agosto de 2026**, elegida a propósito porque:

- contiene el festivo del **7 de agosto** (viernes, Batalla de Boyacá) y los
  domingos **2** y **9**, así que se ven los tres tipos de día;
- cae después del 15-jul-2026, así que usa los parámetros nuevos
  (`horas_quincena=105`, `divisor_hora_ordinaria=210`).

Cada empleado ilustra una función distinta de la aplicación:

| Empleado          | Ilustra                                                  |
|-------------------|----------------------------------------------------------|
| Marcela Osorio    | turnos nocturnos que cruzan medianoche, festivo nocturno |
| Hernán Duque      | turno partido + concepto manual (deducción)              |
| Lucía Cardona     | jornada ordinaria sobre un turno real + turno de relleno |
| Andrés Peláez     | quincena incompleta + auxilio de transporte prorrateado  |

La unidad principal descuenta seguridad social para que el desglose y el Excel
muestren el bloque DEDUCCIONES y el VALOR A PAGAR.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import date, time
from decimal import Decimal

from nomina.dominio.entidades.concepto_liquidado import DEDUCCION, ConceptoManual
from nomina.dominio.entidades.turno import Turno

PERIODO_INICIO = date(2026, 8, 1)
PERIODO_FIN = date(2026, 8, 15)

# Dos quincenas anteriores, solo para que el manual pueda mostrar los tres
# estados de un periodo (abierto / liquidado / cerrado) y las acciones de cada uno.
PERIODO_LIQUIDADO = (date(2026, 7, 16), date(2026, 7, 31))
PERIODO_CERRADO = (date(2026, 7, 1), date(2026, 7, 15))

# Salario mínimo de referencia 2026 usado en el resto de datos del repo.
SALARIO_BASICO = Decimal("1750905")

NOMBRE_UNIDAD = "CONJUNTO LOS ALMENDROS P.H"
NIT = "901555444-1"

NOMBRE_UNIDAD_2 = "EDIFICIO MIRADOR DEL RÍO P.H"
NIT_2 = "901555444-2"

# La demo usa el motor "de fábrica": estrategia global vigente
# (`presupuesto_quincenal`) y el modelo de factores aditivo, sin la tabla de
# factores legada que sí necesitan Puebla y Thunapa. Así el manual explica el
# comportamiento por defecto.
ESTRATEGIA_EXTRAS: str | None = None
FACTORES_OVERRIDE: dict[str, Decimal] = {}

# Se aplica automáticamente a TODOS los empleados de la unidad al liquidar.
CONCEPTOS_FIJOS: tuple[ConceptoManual, ...] = (
    ConceptoManual(nombre="CUOTA DE MANEJO TARJETA", valor=Decimal("7500"), tipo=DEDUCCION),
)

# (nombre, documento, cargo, salario)
EMPLEADOS = [
    ("Marcela Osorio Ríos", "1000000001", "vigilante", SALARIO_BASICO),
    ("Hernán Duque Salazar", "1000000002", "todero", Decimal("1900000")),
    ("Lucía Cardona Vélez", "1000000003", "aseo", SALARIO_BASICO),
    ("Andrés Peláez Mesa", "1000000004", "vigilante", SALARIO_BASICO),
]

EMPLEADOS_2 = [
    ("Sofía Restrepo Ángel", "1000000005", "vigilante", SALARIO_BASICO),
    ("Camilo Ospina Tabares", "1000000006", "aseo", SALARIO_BASICO),
]

# --- Turnos: (día de agosto, hora_inicio, hora_fin, minutos_jornada_ordinaria) -
# `hora_fin <= hora_inicio` significa que el turno cruza medianoche.
# El último elemento es `None` en un turno normal.

TurnoCrudo = tuple[int, time, time, int | None]

_NOCHE = (time(18, 0), time(6, 0))


def _repetir(
    dias: Sequence[int], inicio: time, fin: time, jornada: int | None = None
) -> list[TurnoCrudo]:
    """El mismo horario en varios días."""
    return [(dia, inicio, fin, jornada) for dia in dias]


TURNOS: dict[str, list[TurnoCrudo]] = {
    # Vigilante nocturna: 18:00–06:00, casi día de por medio. Cae en el festivo
    # del 7 y en el domingo 9, así que aparecen recargos festivos y nocturnos.
    # Suma 120 h > 105 del presupuesto: las últimas 15 h se pagan como extra
    # nocturna.
    "1000000001": _repetir((1, 2, 3, 5, 7, 9, 10, 11, 13, 15), *_NOCHE),
    # Todero con turno partido de lunes a viernes (06:00–10:00 y 14:00–18:00),
    # más tres sábados completos: 108 h, o sea 3 h de extra diurna.
    "1000000002": (
        _repetir((3, 4, 5, 6, 10, 11, 12, 13, 14), time(6, 0), time(10, 0))
        + _repetir((3, 4, 5, 6, 10, 11, 12, 13, 14), time(14, 0), time(18, 0))
        + _repetir((1, 8, 15), time(6, 0), time(18, 0))
    ),
    # Aseo: turnos reales de 8 h, más los dos casos de «jornada ordinaria».
    "1000000003": (
        _repetir((3, 4, 5, 6, 10, 11, 12, 13, 14), time(6, 0), time(14, 0))
        # (a) turno REAL del festivo marcado como jornada ordinaria: las primeras
        #     7 h las cubre el salario, solo la 8ª y la 9ª pagan extra festiva.
        + _repetir((7,), time(6, 0), time(15, 0), 420)
        # (b) TURNO DE RELLENO: el día 8 no se trabajó; el turno 06:00–13:00 solo
        #     existe para cuadrar las horas de la quincena.
        + _repetir((8,), time(6, 0), time(13, 0), 420)
    ),
    # Ingresó a mitad de quincena: se marca «quincena incompleta» y el auxilio
    # de transporte se prorratea sobre lo laborado.
    "1000000004": _repetir((8, 10, 12, 14), *_NOCHE),
}

TURNOS_2: dict[str, list[TurnoCrudo]] = {
    "1000000005": _repetir((2, 4, 6, 8, 10, 12, 14), time(6, 0), time(18, 0)),
    "1000000006": _repetir((3, 5, 7, 10, 12, 14), time(7, 0), time(15, 0)),
}

CONCEPTOS_MANUALES: dict[str, tuple[ConceptoManual, ...]] = {
    "1000000002": (
        ConceptoManual(nombre="PRÉSTAMO", valor=Decimal("120000"), tipo=DEDUCCION),
    ),
}

# Marcas por empleado y quincena: (quincena_incompleta, sin_extras, auxilio_por_dias_laborados)
AJUSTES: dict[str, tuple[bool, bool, bool]] = {
    "1000000004": (True, False, True),
}


def turnos_de(documento: str) -> list[Turno]:
    """Turnos del empleado de la unidad principal para la quincena de la demo."""
    return _turnos(TURNOS.get(documento, []))


def turnos_2_de(documento: str) -> list[Turno]:
    """Turnos del empleado de la segunda unidad para la quincena de la demo."""
    return _turnos(TURNOS_2.get(documento, []))


def _turnos(tuplas: list[TurnoCrudo]) -> list[Turno]:
    return [
        Turno(
            fecha=date(2026, 8, dia),
            hora_inicio=inicio,
            hora_fin=fin,
            minutos_jornada_ordinaria=jornada,
        )
        for dia, inicio, fin, jornada in tuplas
    ]
