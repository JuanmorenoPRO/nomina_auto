"""Las dos migraciones que adoptan el criterio legal de horas extra.

`d3b81f6ca427` corrige el cronograma de `jornada_maxima_semanal` y abre la vigencia
de `semanal_legal`; `f2a7c91d40e8` pasa las unidades a esa estrategia y les quita la
tabla de factores combinados legada. Ambas son conservadoras: si el dato ya está
ajustado a mano, no lo pisan.
"""

import os
import subprocess
from datetime import date
from pathlib import Path
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, delete, insert, select, update
from sqlalchemy.orm import Session

from nomina.infraestructura.persistencia.modelos import ParametroLegalModel, UnidadResidencialModel
from nomina.infraestructura.persistencia.sembrar import sembrar_parametros
from nomina.semilla import PARAMETROS_SEMILLA

RAIZ = Path(__file__).resolve().parents[1]
ANTERIOR = "b9e4d17c5a30"  # la revisión previa a las dos nuevas
CRITERIO_LEGAL = "f2a7c91d40e8"  # la última de las dos migraciones de datos

FACTORES_LEGADOS = {
    "extra_diurna_festiva": "2.0",
    "extra_nocturna_festiva": "2.5",
    "festivo_nocturno": "2.1",
}
CONFIG_LEGADA = {
    "estrategia_extras": "jornada",
    "factores_override": FACTORES_LEGADOS,
    "conceptos_fijos": [],
}


def _alembic(url: str, *args: str) -> None:
    r = subprocess.run(
        ["uv", "run", "--no-sync", "alembic", *args],
        cwd=RAIZ, env={"PATH": os.environ["PATH"], "DATABASE_URL": url},
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


def _semilla(codigo: str) -> list[tuple[str, date, date | None]]:
    return sorted(
        (p.valor, p.vigencia.desde, p.vigencia.hasta)
        for p in PARAMETROS_SEMILLA
        if p.codigo == codigo
    )


def _config(engine, nombre: str) -> dict:
    with engine.connect() as c:
        return c.execute(
            select(UnidadResidencialModel.config).where(
                UnidadResidencialModel.nombre == nombre
            )
        ).scalar_one()


@pytest.fixture
def bd(tmp_path):
    url = f"sqlite:///{tmp_path}/m.sqlite3"
    _alembic(url, "upgrade", "head")
    engine = create_engine(url)
    with Session(engine) as s:
        sembrar_parametros(s)
        s.commit()
    return url, engine


def _volver_al_estado_legado(url: str, engine) -> None:
    """Deja la base como estaba antes: parámetros derivados y unidad con config vieja."""
    _alembic(url, "downgrade", ANTERIOR)
    with engine.begin() as c:
        c.execute(
            delete(ParametroLegalModel).where(
                ParametroLegalModel.codigo == "estrategia_clasificacion_extras"
            )
        )
        c.execute(insert(ParametroLegalModel).values(
            id=uuid4(), codigo="estrategia_clasificacion_extras",
            valor="presupuesto_quincenal", vigente_desde=date(2000, 1, 1),
            vigente_hasta=None, norma="semilla vieja"))
        for desde, valor in [(date(2023, 7, 15), "46"), (date(2024, 7, 15), "45")]:
            c.execute(
                update(ParametroLegalModel)
                .where(
                    ParametroLegalModel.codigo == "jornada_maxima_semanal",
                    ParametroLegalModel.vigente_desde == desde,
                )
                .values(valor=valor)
            )
        c.execute(insert(UnidadResidencialModel).values(
            id=uuid4(), nombre="EDIFICIO LEGADO P.H", nit="900000001",
            activa=True, descuenta_seguridad_social=True, config=CONFIG_LEGADA))


def test_corrige_el_cronograma_de_la_jornada_maxima(bd):
    url, engine = bd
    _volver_al_estado_legado(url, engine)
    _alembic(url, "upgrade", "head")
    assert _vigencias(engine, "jornada_maxima_semanal") == _semilla("jornada_maxima_semanal")


def test_abre_la_vigencia_de_semanal_legal(bd):
    url, engine = bd
    _volver_al_estado_legado(url, engine)
    _alembic(url, "upgrade", "head")
    assert _vigencias(engine, "estrategia_clasificacion_extras") == [
        ("presupuesto_quincenal", date(2000, 1, 1), date(2026, 7, 14)),
        ("semanal_legal", date(2026, 7, 15), None),
    ]


def test_la_unidad_pasa_a_semanal_legal_sin_factores_legados(bd):
    url, engine = bd
    _volver_al_estado_legado(url, engine)
    _alembic(url, "upgrade", "head")
    config = _config(engine, "EDIFICIO LEGADO P.H")
    assert config["estrategia_extras"] == "semanal_legal"
    assert config["factores_override"] == {}


def test_los_conceptos_fijos_de_la_unidad_no_se_tocan(bd):
    """La cuota de manejo de Puebla vive en el mismo JSON: no debe perderse."""
    url, engine = bd
    _volver_al_estado_legado(url, engine)
    cuota = {"nombre": "CUOTA DE MANEJO", "valor": "7095",
             "tipo": "devengado", "salarial": False}
    with engine.begin() as c:
        c.execute(
            update(UnidadResidencialModel)
            .where(UnidadResidencialModel.nombre == "EDIFICIO LEGADO P.H")
            .values(config={**CONFIG_LEGADA, "conceptos_fijos": [cuota]})
        )
    _alembic(url, "upgrade", "head")
    assert _config(engine, "EDIFICIO LEGADO P.H")["conceptos_fijos"] == [cuota]


def test_no_pisa_una_unidad_ya_ajustada_a_mano(bd):
    url, engine = bd
    _volver_al_estado_legado(url, engine)
    a_mano = {"estrategia_extras": "diaria", "factores_override": {"extra_diurna": "1.3"},
              "conceptos_fijos": []}
    with engine.begin() as c:
        c.execute(
            update(UnidadResidencialModel)
            .where(UnidadResidencialModel.nombre == "EDIFICIO LEGADO P.H")
            .values(config=a_mano)
        )
    _alembic(url, "upgrade", "head")
    assert _config(engine, "EDIFICIO LEGADO P.H") == a_mano


def test_el_downgrade_devuelve_el_estado_legado(bd):
    url, engine = bd
    _volver_al_estado_legado(url, engine)
    _alembic(url, "upgrade", "head")
    _alembic(url, "downgrade", ANTERIOR)
    assert _config(engine, "EDIFICIO LEGADO P.H") == CONFIG_LEGADA
    assert _vigencias(engine, "estrategia_clasificacion_extras") == [
        ("presupuesto_quincenal", date(2000, 1, 1), None)
    ]
    jornada = dict((d, v) for v, d, _ in _vigencias(engine, "jornada_maxima_semanal"))
    assert jornada[date(2023, 7, 15)] == "46"
    assert jornada[date(2024, 7, 15)] == "45"


def test_sobre_una_base_nueva_y_sana_no_cambia_nada(bd):
    """Base sembrada con la semilla nueva: reaplicar las migraciones es un no-op."""
    url, engine = bd
    antes_jornada = _vigencias(engine, "jornada_maxima_semanal")
    antes_estrategia = _vigencias(engine, "estrategia_clasificacion_extras")
    # A las revisiones concretas, no a `head`: `stamp` no toca el esquema, así que
    # subir hasta head reaplicaría el `add_column` de la migración posterior.
    _alembic(url, "stamp", ANTERIOR)
    _alembic(url, "upgrade", CRITERIO_LEGAL)
    assert _vigencias(engine, "jornada_maxima_semanal") == antes_jornada
    assert _vigencias(engine, "estrategia_clasificacion_extras") == antes_estrategia
