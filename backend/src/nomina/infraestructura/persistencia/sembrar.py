"""Siembra de parámetros legales iniciales (idempotente: solo si la tabla está vacía).

Uso directo:  uv run python -m nomina.infraestructura.persistencia.sembrar
También se ejecuta al arrancar la API.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from nomina.infraestructura.persistencia.modelos import ParametroLegalModel
from nomina.infraestructura.persistencia.repositorios import RepositorioParametrosSQL
from nomina.semilla import PARAMETROS_SEMILLA


def sembrar_parametros(session: Session) -> int:
    """Inserta los parámetros de la semilla cuyo código aún no existe en la BD.

    Idempotente por código: en una BD nueva inserta todo; en una ya sembrada
    agrega solo los códigos nuevos (ej. aportes de seguridad social) sin duplicar.
    """
    existentes = set(session.scalars(select(ParametroLegalModel.codigo)))
    repo = RepositorioParametrosSQL(session)
    insertados = 0
    for parametro in PARAMETROS_SEMILLA:
        if parametro.codigo in existentes:
            continue
        repo.agregar(parametro)
        insertados += 1
    return insertados


def main() -> None:
    from nomina.infraestructura.persistencia.base import crear_engine, fabrica_sesiones

    engine = crear_engine()
    with fabrica_sesiones(engine)() as session:
        insertados = sembrar_parametros(session)
        session.commit()
    print(f"Parámetros insertados: {insertados}")


if __name__ == "__main__":
    main()
