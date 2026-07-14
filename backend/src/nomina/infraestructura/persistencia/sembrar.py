"""Siembra de parámetros legales iniciales (idempotente: solo si la tabla está vacía).

Uso directo:  uv run python -m nomina.infraestructura.persistencia.sembrar
También se ejecuta al arrancar la API.
"""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from nomina.infraestructura.persistencia.modelos import ParametroLegalModel
from nomina.infraestructura.persistencia.repositorios import RepositorioParametrosSQL
from nomina.semilla import PARAMETROS_SEMILLA


def sembrar_parametros(session: Session) -> int:
    """Inserta la semilla si no hay parámetros. Devuelve cuántos insertó."""
    existentes = session.scalar(select(func.count()).select_from(ParametroLegalModel))
    if existentes:
        return 0
    repo = RepositorioParametrosSQL(session)
    for parametro in PARAMETROS_SEMILLA:
        repo.agregar(parametro)
    return len(PARAMETROS_SEMILLA)


def main() -> None:
    from nomina.infraestructura.persistencia.base import crear_engine, fabrica_sesiones

    engine = crear_engine()
    with fabrica_sesiones(engine)() as session:
        insertados = sembrar_parametros(session)
        session.commit()
    print(f"Parámetros insertados: {insertados}")


if __name__ == "__main__":
    main()
