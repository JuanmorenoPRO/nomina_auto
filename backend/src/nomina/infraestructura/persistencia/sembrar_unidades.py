"""Carga las 5 unidades de julio 2026 con sus empleados (idempotente por nombre).

Solo unidades + empleados (sin turnos ni liquidación). Fuente: planillas de la
contadora (SUIZA, RIO CLARO, LORENA, DEL VALLE, ALTO VERDE). Todas descuentan
seguridad social; salario base uniforme; `cargo` genérico (el Excel no lo trae) y
`config` por defecto.

Uso:  uv run python -m nomina.infraestructura.persistencia.sembrar_unidades
"""

from __future__ import annotations

from decimal import Decimal
from uuid import uuid4

from sqlalchemy.orm import Session

from nomina.dominio.entidades.empleado import Empleado
from nomina.dominio.entidades.unidad_residencial import ConfiguracionUnidad, UnidadResidencial
from nomina.infraestructura.persistencia.repositorios import (
    RepositorioEmpleadosSQL,
    RepositorioUnidadesSQL,
)

SALARIO_BASICO = Decimal("1750905")
CARGO = "empleado"

# (nombre_unidad, nit, [(nombre_empleado, documento), ...])
UNIDADES: list[tuple[str, str, list[tuple[str, str]]]] = [
    (
        "PARCELACION LA SUIZA P.H",
        "900232991",
        [
            ("JOHN ESTEBAN LOPEZ GOMEZ", "1026145433"),
            ("GRAJALES LOPEZ RUBIEL DE JESUS", "70855906"),
        ],
    ),
    (
        "EDIFICIO RIO CLARO P.H",
        "800084755",
        [
            ("FREDY SEPULVEDA", "15536952"),
            ("RIGOBERTO MARIN", "71392880"),
            ("WALTER GOMEZ", "71878165"),
            ("OLGA PIEDRAHITA", "43581748"),
        ],
    ),
    (
        "EDIFICIO LORENA P.H",
        "890981800",
        [
            ("ELKIN DE JESUS HERNANDEZ", "70565690"),
            ("HERNAN DARIO PALACIO", "15457723"),
        ],
    ),
    (
        "EDIFICIO DEL VALLE P.H",
        "800006208",
        [
            ("CARLOS MARIO MARULANDA", "71705653"),
            ("ELKIN DARIO BURITICA", "70783098"),
            ("JUAN ESTEBAN RESTREPO", "1036640852"),
        ],
    ),
    (
        "EDIFICIO ALTO VERDE P.H",
        "800.233.243-5",
        [
            ("JORGE IVAN AGUDELO DAVID", "98567498"),
        ],
    ),
]


def sembrar_unidades(session: Session) -> tuple[list[str], int]:
    """Crea las unidades que aún no existan (por nombre) con sus empleados.

    Idempotente: una unidad ya presente se omite por completo (con sus empleados).
    Devuelve (nombres de unidades creadas, total de empleados creados).
    """
    unidades_repo = RepositorioUnidadesSQL(session)
    empleados_repo = RepositorioEmpleadosSQL(session)

    existentes = {u.nombre for u in unidades_repo.listar()}
    creadas: list[str] = []
    empleados_creados = 0

    for nombre, nit, empleados in UNIDADES:
        if nombre in existentes:
            continue

        unidad = UnidadResidencial(
            id=uuid4(),
            nombre=nombre,
            nit=nit,
            descuenta_seguridad_social=True,
            config=ConfiguracionUnidad(),
        )
        unidades_repo.guardar(unidad)

        for nombre_emp, documento in empleados:
            empleados_repo.guardar(
                Empleado(
                    id=uuid4(),
                    unidad_id=unidad.id,
                    nombre=nombre_emp,
                    documento=documento,
                    cargo=CARGO,
                    salario_base=SALARIO_BASICO,
                )
            )
            empleados_creados += 1

        creadas.append(nombre)

    return creadas, empleados_creados


def main() -> None:
    from nomina.infraestructura.persistencia.base import crear_engine, fabrica_sesiones

    engine = crear_engine()
    with fabrica_sesiones(engine)() as session:
        creadas, empleados_creados = sembrar_unidades(session)
        session.commit()

    total = len(UNIDADES)
    print(
        f"Unidades creadas: {len(creadas)}/{total} "
        f"(ya existían: {total - len(creadas)}). Empleados creados: {empleados_creados}."
    )
    for nombre in creadas:
        print(f"  + {nombre}")


if __name__ == "__main__":
    main()
