#!/usr/bin/env python
"""Impacto en pesos de adoptar el criterio legal de horas extra.

Compara, sobre los turnos REALES de la base, la liquidación con la config anterior
(`jornada` + tabla de factores legada) contra la nueva (`semanal_legal` + factores
aditivos vigentes), por unidad y empleado, en los periodos ABIERTOS.

Es de SOLO LECTURA: no escribe, no liquida, no toca ninguna versión. Sirve para
mostrarle el número a las copropiedades antes de reliquidar desde la UI.

Uso:
    DATABASE_URL=postgresql://... uv run python scripts/impacto-criterio-legal.py
    # o contra la base local:
    uv run python scripts/impacto-criterio-legal.py --periodo 2026-08-16
"""

from __future__ import annotations

import argparse
import os
import sys
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend" / "src"))

from sqlalchemy import create_engine  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

from nomina.dominio.entidades.parametro_legal import ConjuntoParametros  # noqa: E402
from nomina.infraestructura.config import Settings  # noqa: E402
from nomina.dominio.servicios.calculadora import liquidar  # noqa: E402
from nomina.dominio.servicios.calendario_festivos import CalendarioFestivos  # noqa: E402
from nomina.dominio.servicios.clasificador_extras import clasificar_extras  # noqa: E402
from nomina.dominio.servicios.segmentador import segmentar_turnos  # noqa: E402
from nomina.infraestructura.persistencia.repositorios import (  # noqa: E402
    RepositorioAjustesQuincenaSQL,
    RepositorioConceptosManualesSQL,
    RepositorioEmpleadosSQL,
    RepositorioFestivosSQL,
    RepositorioParametrosSQL,
    RepositorioPeriodosSQL,
    RepositorioTurnosSQL,
    RepositorioUnidadesSQL,
)

FACTORES_LEGADOS = {
    "extra_diurna_festiva": Decimal("2.0"),
    "extra_nocturna_festiva": Decimal("2.5"),
    "festivo_nocturno": Decimal("2.1"),
}


def _liquidar_empleado(session, empleado, unidad, periodo, parametros, calendario, *, legal):
    turnos_repo = RepositorioTurnosSQL(session)
    ajustes = RepositorioAjustesQuincenaSQL(session)
    registrados = turnos_repo.de_empleado_entre(
        empleado.id, periodo.fecha_inicio, periodo.fecha_fin
    )
    tramos = segmentar_turnos([r.turno for r in registrados], parametros, calendario)

    contexto = ()
    if legal:
        lunes = periodo.fecha_inicio - timedelta(days=periodo.fecha_inicio.weekday())
        previos = turnos_repo.de_empleado_entre(
            empleado.id, lunes - timedelta(days=1), periodo.fecha_inicio - timedelta(days=1)
        )
        contexto = segmentar_turnos([r.turno for r in previos], parametros, calendario)

    clasificados = clasificar_extras(
        tramos,
        parametros,
        periodo.fecha_inicio,
        estrategia="semanal_legal" if legal else "jornada",
        tramos_contexto=contexto,
    )
    manuales = unidad.config.conceptos_fijos + tuple(
        RepositorioConceptosManualesSQL(session).de_empleado_en_periodo(
            empleado.id, periodo.id
        )
    )
    por_dias = ajustes.auxilio_por_dias_laborados(empleado.id, periodo.id)
    return liquidar(
        clasificados,
        empleado.salario_base,
        parametros,
        periodo.fecha_inicio,
        incluir_auxilio_transporte=por_dias
        or not (empleado.incapacitado or empleado.ocasional),
        auxilio_prorrateado=por_dias,
        factores_override=None if legal else FACTORES_LEGADOS,
        conceptos_manuales=manuales,
        descontar_seguridad_social=unidad.descuenta_seguridad_social,
        quincena_completa=not ajustes.quincena_incompleta(empleado.id, periodo.id),
        pagar_dia_31=ajustes.pagar_dia_31(empleado.id, periodo.id),
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--periodo", action="append",
        help="fecha de inicio (AAAA-MM-DD). Por defecto, todos los periodos abiertos.",
    )
    args = parser.parse_args()

    # `Settings` reescribe postgres:// → postgresql+psycopg:// igual que la app.
    url = Settings(
        database_url=os.environ.get("DATABASE_URL", "sqlite:///./backend/nomina_dev.sqlite3")
    ).database_url
    engine = create_engine(url)
    total_general = 0

    with Session(engine) as session:
        parametros = ConjuntoParametros(
            parametros=tuple(RepositorioParametrosSQL(session).listar())
        )
        agregados, anulados = RepositorioFestivosSQL(session).ajustes()
        calendario = CalendarioFestivos(festivos_manuales=agregados, no_festivos=anulados)

        periodos = RepositorioPeriodosSQL(session).listar()
        if args.periodo:
            elegidos = {date.fromisoformat(p) for p in args.periodo}
            periodos = [p for p in periodos if p.fecha_inicio in elegidos]
        else:
            periodos = [p for p in periodos if p.estado.value == "abierto"]

        unidades = RepositorioUnidadesSQL(session).listar()
        empleados_repo = RepositorioEmpleadosSQL(session)

        for periodo in sorted(periodos, key=lambda p: p.fecha_inicio):
            print(f"\n{'=' * 78}\nPERIODO {periodo.fecha_inicio} → {periodo.fecha_fin}\n{'=' * 78}")
            print(f"{'EMPLEADO':34s} {'ANTES':>12s} {'CRITERIO LEGAL':>15s} {'DIFERENCIA':>13s}")
            for unidad in sorted(unidades, key=lambda u: u.nombre):
                empleados = empleados_repo.listar(unidad_id=unidad.id, solo_activos=True)
                if not empleados:
                    continue
                subtotal = 0
                print(f"\n  {unidad.nombre}")
                for empleado in empleados:
                    antes = _liquidar_empleado(
                        session, empleado, unidad, periodo, parametros, calendario, legal=False
                    )
                    ahora = _liquidar_empleado(
                        session, empleado, unidad, periodo, parametros, calendario, legal=True
                    )
                    delta = int(ahora.neto_a_pagar - antes.neto_a_pagar)
                    subtotal += delta
                    aviso = " ⚠ sin hora base" if ahora.minutos_sin_hora_base else ""
                    print(
                        f"    {empleado.nombre[:32]:32s} "
                        f"{int(antes.neto_a_pagar):>12,} {int(ahora.neto_a_pagar):>15,} "
                        f"{delta:>+13,}{aviso}"
                    )
                print(f"    {'subtotal unidad':32s} {'':>12s} {'':>15s} {subtotal:>+13,}")
                total_general += subtotal

    print(f"\n{'=' * 78}\nDIFERENCIA TOTAL EN LOS PERIODOS ANALIZADOS: {total_general:+,}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
