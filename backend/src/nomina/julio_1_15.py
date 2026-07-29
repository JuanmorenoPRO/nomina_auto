"""Datos de la quincena 1-15 jul 2026 para las unidades cuya planilla real llegó
en Excel (SANTA RITA, CASA BLANCA, SUIZA, RIO CLARO, LORENA, DEL VALLE, ALTO VERDE).

Mismo enfoque que EDIFICIO PUEBLA P.H (`puebla.py`): los turnos están reconstruidos
—no son el horario real— para que la segmentación del motor + la estrategia
`jornada` reproduzcan el TOTAL de horas por concepto de cada planilla (no el
detalle día a día, que en varias planillas de la contadora es inconsistente con
un calendario puro: mismo turno nocturno partido entre "nocturno" y "nocturno
dominical" en un mismo día, horas de un turno que cruza medianoche atribuidas al
día equivocado). Ver [[proyecto-nomina-residencial]].

Fuente: JULIO SANTA RITA 2026.xlsx, CASA BLANCA JULIO 2026.xlsx,
SUIZA JULIO 2026.xlsx + NOMINA JULIO 1 AL 15.xls (horario real de John/Rubiel),
JULIO RIO CLARO 2026.xlsx, JULIO 2026 LORENA.xlsx, DEL VALLE JULIO 2026.xlsx,
JULIO ALTO VERDE 2026.xlsx.

Huecos conocidos (motor no los modela; ver memoria `proyecto-nomina-residencial`):
- El salario base y el auxilio de transporte son SIEMPRE de quincena completa
  (`liquidar_quincena.py` no prorratea). Empleados con periodo parcial
  (Rigoberto y Olga, Rio Claro, solo 12 de 15 días) o sin auxilio ese periodo
  (Doris, Rubiel —recibe auxilio de moto en su lugar—, Elkin Hernández de
  Lorena) quedarán con un total_devengado MAYOR que el real. Documentado,
  aceptado por el usuario para esta quincena histórica.
- Doris (Casa Blanca) no se descuenta pensión (trámite de jubilación) — se
  maneja con `descuenta_seguridad_social=False` en la unidad + una deducción
  manual de SALUD equivalente, en vez del descuento automático.
"""

from __future__ import annotations

from datetime import date, time
from decimal import Decimal

from nomina.dominio.entidades.concepto_liquidado import DEDUCCION, DEVENGADO, ConceptoManual
from nomina.dominio.entidades.turno import Turno

PERIODO_INICIO = date(2026, 7, 1)
PERIODO_FIN = date(2026, 7, 15)
SALARIO_BASICO = Decimal("1750905")

# Misma tabla de factores legada que EDIFICIO PUEBLA P.H (ver `puebla.py` y
# `sembrar_unidades.py`): confirmada al peso contra SUIZA JULIO 2026.xlsx.
ESTRATEGIA_EXTRAS = "jornada"
FACTORES_OVERRIDE: dict[str, Decimal] = {
    "extra_diurna_festiva": Decimal("2.0"),
    "extra_nocturna_festiva": Decimal("2.5"),
    "festivo_nocturno": Decimal("2.1"),
}

# --- Unidades nuevas (no estaban en `sembrar_unidades.py`) ---------------------

SANTA_RITA_NOMBRE = "EDIFICIO SANTA RITA REAL P.H"
SANTA_RITA_NIT = "900.088.189-6"

CASA_BLANCA_NOMBRE = "EDIFICIO CASA BLANCA"
CASA_BLANCA_NIT = "890908604"

# --- Turnos reconstruidos por documento: (día, hora_inicio, hora_fin) ---------
# hora_fin puede pasarse de 24 (cruza medianoche) o traer .5 (media hora).

TURNOS: dict[str, list[tuple[int, float, float]]] = {
    # EDIFICIO SANTA RITA REAL P.H. — GABRIEL JOAQUIN TORRES TORRES
    "98567498-2": [
        (1, 7, 15), (2, 7, 15), (3, 7, 15), (4, 7, 14), (6, 7, 15), (7, 7, 15),
        (8, 7, 15), (9, 7, 14), (10, 7, 15), (11, 7, 10), (14, 7, 15), (15, 7, 15),
    ],
    # EDIFICIO CASA BLANCA — DORIS CECILIA BOLIVAR ESPINOSA
    "43321643": [
        (1, 7, 15), (2, 7, 15), (3, 7, 15), (4, 7, 15), (6, 7, 15), (7, 7, 15),
        (8, 7, 15), (9, 7, 15), (10, 7, 15), (11, 7, 15), (14, 7, 15),
    ],
    # PARCELACION LA SUIZA P.H — JOHN ESTEBAN LOPEZ GOMEZ (horario real del .xls)
    "1026145433": [
        (1, 7, 15), (2, 7, 15), (3, 7, 15), (6, 7, 15), (7, 7, 15), (8, 7, 15),
        (9, 7, 15), (10, 7, 15), (11, 7, 15), (12, 7, 19), (13, 7, 15),
        (14, 7, 15), (15, 7, 15),
    ],
    # PARCELACION LA SUIZA P.H — GRAJALES LOPEZ RUBIEL DE JESUS (horario real, turno partido)
    "70855906": [
        (1, 7, 11), (1, 15, 19), (2, 7, 11), (2, 15, 19), (3, 7, 11), (3, 15, 19),
        (4, 7, 15), (5, 7, 19), (6, 7, 11), (6, 15, 19), (7, 7, 11), (7, 15, 19),
        (8, 7, 11), (8, 15, 19), (9, 7, 11), (9, 15, 19), (10, 7, 11), (10, 15, 19),
        (13, 7, 11), (13, 15, 19), (14, 7, 11), (14, 15, 19), (15, 7, 11), (15, 15, 19),
    ],
    # EDIFICIO RIO CLARO P.H — FREDY SEPULVEDA
    "15536952": [
        (5, 6, 11), (5, 19, 22), (12, 19, 27), (13, 0, 6), (13, 19, 21),
        (1, 6, 19), (2, 6, 19), (3, 6, 19), (4, 6, 17),
        (6, 19, 30), (7, 19, 30), (8, 19, 29), (9, 19, 27), (10, 19, 26),
    ],
    # EDIFICIO RIO CLARO P.H — RIGOBERTO MARIN (periodo parcial 4-15 en la planilla real)
    "71392880": [
        (5, 6, 14), (12, 6, 14), (13, 0, 6), (13, 19, 21),
        (1, 19, 30), (2, 19, 30), (3, 19, 29), (6, 19, 27), (7, 19, 25),
    ],
    # EDIFICIO RIO CLARO P.H — WALTER GOMEZ
    "71878165": [
        (2, 11, 30), (3, 19, 30), (6, 19, 27), (7, 19, 27), (8, 19, 22),
        (5, 6, 14), (12, 6, 14), (13, 15, 17), (13, 0, 4),
        (1, 6, 19), (4, 8, 19), (9, 6, 16), (11, 6, 16),
    ],
    # EDIFICIO RIO CLARO P.H — OLGA PIEDRAHITA (periodo parcial 4-15 en la planilla real)
    "43581748": [
        (4, 7, 15), (6, 7, 15), (7, 7, 15), (8, 7, 15), (9, 7, 15),
        (10, 7, 15), (14, 7, 15), (15, 7, 11),
    ],
    # EDIFICIO LORENA P.H — HERNAN DARIO PALACIO
    "15457723": [
        (5, 6, 14), (12, 6, 14), (13, 6, 14),
    ],
    # EDIFICIO LORENA P.H — ELKIN DE JESUS HERNANDEZ: sin turnos (ausente todo el periodo)
    "70565690": [],
    # EDIFICIO DEL VALLE P.H — CARLOS MARIO MARULANDA
    "71705653": [(d, 7, 14.5) for d in (1, 2, 3, 4, 6, 7, 8, 9, 10, 11, 14, 15)],
    # EDIFICIO DEL VALLE P.H — ELKIN DARIO BURITICA
    "70783098": [(d, 7, 14.5) for d in (1, 2, 3, 4, 6, 7, 8, 9, 10, 11, 14, 15)],
    # EDIFICIO DEL VALLE P.H — JUAN ESTEBAN RESTREPO
    "1036640852": [
        (1, 6, 19), (2, 6, 15), (3, 19, 30), (6, 19, 28),
        (7, 19, 27), (8, 19, 27), (9, 19, 27), (10, 19, 27), (14, 19, 21),
        (5, 7, 19), (12, 6, 7), (5, 0, 6), (5, 20, 24), (12, 19, 27), (13, 19, 24),
    ],
    # EDIFICIO ALTO VERDE P.H — JORGE IVAN AGUDELO DAVID
    "98567498": [(1, 6, 17.5), (2, 19, 20.5)],
}

# --- Conceptos manuales por documento (devengados/deducciones cargados a mano) -

CONCEPTOS_MANUALES: dict[str, tuple[ConceptoManual, ...]] = {
    "1026145433": (  # JOHN — arrastre de junio, no es de esta quincena pero la contadora lo sumó aquí
        ConceptoManual(nombre="4 HORAS EXTRAS DIA 25 JUNIO", valor=Decimal("36610"),
                        tipo=DEVENGADO, salarial=True),
    ),
    "1036640852": (  # JUAN — ver nota de huecos conocidos: capacidad física de solo 3 días
        # especiales (5, 12, 13 jul) para nocturno dominical; faltan 12 h vs. planilla real.
        ConceptoManual(
            nombre="AJUSTE RECONSTRUCCION NOCTURNO DOMINICAL (limite de 3 dias especiales en jul 1-15)",
            valor=Decimal("200557"), tipo=DEVENGADO, salarial=True,
        ),
    ),
    "98567498": (  # JORGE
        ConceptoManual(nombre="DEDUCCION PRESTAMO", valor=Decimal("50000"), tipo=DEDUCCION),
    ),
    "71392880": (  # RIGOBERTO
        ConceptoManual(nombre="DEDUCCION PRESTAMO", valor=Decimal("50000"), tipo=DEDUCCION),
    ),
    "43321643": (  # DORIS — sin descuento de pensión (trámite de jubilación); solo salud manual
        ConceptoManual(nombre="SALUD", valor=Decimal("35018"), tipo=DEDUCCION),
        ConceptoManual(nombre="DEDUCCION 4 DIAS AUX TRANSPORTE (INCAPACIDAD JUN)",
                        valor=Decimal("33213"), tipo=DEDUCCION),
        ConceptoManual(nombre="DESCUENTO PRESTAMO", valor=Decimal("500000"), tipo=DEDUCCION),
    ),
    "70855906": (  # RUBIEL
        ConceptoManual(nombre="DEDUCCION ARRIENDO", valor=Decimal("110500"), tipo=DEDUCCION),
    ),
}


def turnos_de(documento: str) -> list[Turno]:
    """Objetos Turno del empleado para la quincena 1-15 jul 2026."""
    resultado = []
    for dia, hi, hf in TURNOS.get(documento, []):
        hi_h, hi_m = int(hi % 24), round((hi % 24 - int(hi % 24)) * 60)
        hf_h, hf_m = int(hf % 24), round((hf % 24 - int(hf % 24)) * 60)
        resultado.append(
            Turno(fecha=date(2026, 7, dia), hora_inicio=time(hi_h, hi_m), hora_fin=time(hf_h, hf_m))
        )
    return resultado
