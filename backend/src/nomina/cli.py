"""CLI mínimo para probar el motor de cálculo a mano (Fase 1).

Ejemplo:
    uv run python -m nomina.cli --salario 2200000 --desde 2026-07-01 \
        --turno "2026-07-04 18:00-06:00" --turno "2026-07-05 18:00-06:00"
"""

from __future__ import annotations

import argparse
from datetime import date, time
from decimal import Decimal

from nomina.dominio.entidades.turno import Turno, validar_sin_solapamientos
from nomina.dominio.servicios.calculadora import liquidar
from nomina.dominio.servicios.calendario_festivos import CalendarioFestivos
from nomina.dominio.servicios.clasificador_extras import clasificar_extras
from nomina.dominio.servicios.segmentador import segmentar_turnos
from nomina.semilla import parametros_semilla


def _parsear_turno(texto: str) -> Turno:
    """Formato: 'AAAA-MM-DD HH:MM-HH:MM' (fin ≤ inicio = cruza medianoche)."""
    try:
        fecha_txt, horas = texto.split(" ")
        inicio_txt, fin_txt = horas.split("-")
        return Turno(
            fecha=date.fromisoformat(fecha_txt),
            hora_inicio=time.fromisoformat(inicio_txt),
            hora_fin=time.fromisoformat(fin_txt),
        )
    except ValueError as e:
        raise SystemExit(f"Turno inválido '{texto}' (formato: AAAA-MM-DD HH:MM-HH:MM): {e}")


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Liquidación de prueba de una quincena")
    parser.add_argument("--salario", type=Decimal, required=True, help="salario básico mensual")
    parser.add_argument("--desde", type=date.fromisoformat, required=True,
                        help="inicio del periodo (fija vigencias del periodo)")
    parser.add_argument("--turno", action="append", default=[], metavar="'AAAA-MM-DD HH:MM-HH:MM'")
    parser.add_argument("--estrategia", choices=["presupuesto_quincenal", "semanal_legal"],
                        default=None, help="anula la estrategia del parámetro")
    parser.add_argument("--sin-auxilio", action="store_true")
    parser.add_argument("--tramos", action="store_true", help="mostrar el detalle de tramos")
    args = parser.parse_args(argv)

    parametros = parametros_semilla()
    calendario = CalendarioFestivos()
    turnos = [_parsear_turno(t) for t in args.turno]
    validar_sin_solapamientos(turnos)

    tramos = segmentar_turnos(turnos, parametros, calendario)
    clasificados = clasificar_extras(tramos, parametros, args.desde, args.estrategia)

    if args.tramos:
        print(f"{'INICIO':<17}{'FIN':<7}{'MIN':>5}  {'FRANJA':<9}{'DÍA':<11}EXTRA")
        for t in clasificados:
            print(
                f"{t.inicio:%Y-%m-%d %H:%M}  {t.fin:%H:%M}{t.minutos:>6}  "
                f"{t.franja.value:<9}{t.tipo_dia.value:<11}{'sí' if t.es_extra else ''}"
            )
        print()

    resultado = liquidar(
        clasificados, args.salario, parametros, args.desde,
        incluir_auxilio_transporte=not args.sin_auxilio,
    )

    print(f"Tarifa hora ordinaria: {resultado.tarifa_hora:.2f}")
    print(f"{'CONCEPTO':<42}{'HORAS':>7}{'FACTOR':>8}{'VALOR':>14}")
    for c in resultado.conceptos:
        horas = f"{c.horas:.2f}" if c.minutos else ""
        factor = f"{c.factor:.2f}" if c.factor is not None else ""
        print(f"{c.nombre:<42}{horas:>7}{factor:>8}{c.valor:>14,.0f}")
    print(f"{'TOTAL DEVENGADO':<42}{'':>15}{resultado.total:>14,.0f}")


if __name__ == "__main__":
    main()
