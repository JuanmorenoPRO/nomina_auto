"""La migración que corrige `horas_quincena` sobre bases ya derivadas.

Reproduce el estado real que tenía la base del usuario —una sola vigencia de 110
abierta, porque `sembrar_parametros` es idempotente POR CÓDIGO y nunca insertó la
de 105— y verifica que `alembic upgrade head` la deja igual que la semilla.
"""

import subprocess
from datetime import date
from pathlib import Path
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, delete, insert, select
from sqlalchemy.orm import Session

from nomina.infraestructura.persistencia.modelos import ParametroLegalModel
from nomina.infraestructura.persistencia.sembrar import sembrar_parametros
from nomina.semilla import PARAMETROS_SEMILLA

RAIZ = Path(__file__).resolve().parents[1]


def _alembic(url: str, *args: str) -> None:
    r = subprocess.run(
        ["uv", "run", "--no-sync", "alembic", *args],
        cwd=RAIZ, env={"PATH": __import__("os").environ["PATH"], "DATABASE_URL": url},
        capture_output=True, text=True,
    )
    assert r.returncode == 0, r.stderr


def _vigencias(engine, codigo: str) -> list[tuple[str, date, date | None]]:
    with engine.connect() as c:
        filas = c.execute(
            select(
                ParametroLegalModel.valor,
                ParametroLegalModel.vigente_desde,
                ParametroLegalModel.vigente_hasta,
            ).where(ParametroLegalModel.codigo == codigo)
        ).all()
    return sorted((v, d, h) for v, d, h in filas)


ESPERADO = sorted(
    (p.valor, p.vigencia.desde, p.vigencia.hasta)
    for p in PARAMETROS_SEMILLA
    if p.codigo == "horas_quincena"
)


@pytest.fixture
def bd(tmp_path):
    url = f"sqlite:///{tmp_path}/m.sqlite3"
    _alembic(url, "upgrade", "head")
    return url, create_engine(url)


def test_corrige_la_base_derivada(bd):
    """Una sola fila de 110 abierta → queda partida en 110 (hasta 14-jul) y 105."""
    url, engine = bd
    with engine.begin() as c:
        c.execute(delete(ParametroLegalModel).where(
            ParametroLegalModel.codigo == "horas_quincena"))
        c.execute(insert(ParametroLegalModel).values(
            id=uuid4(), codigo="horas_quincena", valor="110",
            vigente_desde=date(2000, 1, 1), vigente_hasta=None, norma="semilla vieja"))
    _alembic(url, "downgrade", "a8d3f5b71c26")
    _alembic(url, "upgrade", "head")
    assert _vigencias(engine, "horas_quincena") == ESPERADO


def test_reaplicarla_sobre_una_base_correcta_no_cambia_nada(bd):
    """Idempotente: sobre la base ya correcta la migración no toca el dato.

    Las migraciones solo crean el esquema; los parámetros los siembra la app al
    arrancar, así que hay que sembrar para tener el estado «base nueva y sana».
    """
    url, engine = bd
    with Session(engine) as s:
        sembrar_parametros(s)
        s.commit()
    antes = _vigencias(engine, "horas_quincena")
    assert antes == ESPERADO
    # A la revisión concreta, no a `head`: `stamp` no toca el esquema, así que
    # subir hasta head reaplicaría también las migraciones posteriores.
    _alembic(url, "stamp", "a8d3f5b71c26")
    _alembic(url, "upgrade", "c1b7e40a9f38")
    assert _vigencias(engine, "horas_quincena") == antes


def test_respeta_una_vigencia_puesta_a_mano(bd):
    """Si alguien ya creó a mano una vigencia desde el corte, no se pisa."""
    url, engine = bd
    manual = [("110", date(2000, 1, 1), date(2026, 7, 14)),
              ("100", date(2026, 7, 15), None)]
    with engine.begin() as c:
        c.execute(delete(ParametroLegalModel).where(
            ParametroLegalModel.codigo == "horas_quincena"))
        for valor, desde, hasta in manual:
            c.execute(insert(ParametroLegalModel).values(
                id=uuid4(), codigo="horas_quincena", valor=valor,
                vigente_desde=desde, vigente_hasta=hasta, norma="a mano"))
    _alembic(url, "downgrade", "a8d3f5b71c26")
    _alembic(url, "upgrade", "head")
    assert _vigencias(engine, "horas_quincena") == sorted(manual)
