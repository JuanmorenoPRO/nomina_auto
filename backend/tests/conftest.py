from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from nomina.infraestructura.api.app import crear_app
from nomina.infraestructura.persistencia.base import Base, fabrica_sesiones, sesion
from nomina.infraestructura.persistencia.sembrar import sembrar_parametros


@pytest.fixture
def session() -> Iterator[Session]:
    """BD SQLite en memoria, migrada y con parámetros sembrados."""
    engine = create_engine(
        "sqlite://", poolclass=StaticPool, connect_args={"check_same_thread": False}
    )
    Base.metadata.create_all(engine)
    with fabrica_sesiones(engine)() as s:
        sembrar_parametros(s)
        s.commit()
        yield s


@pytest.fixture
def client(session: Session) -> Iterator[TestClient]:
    app = crear_app()

    def _sesion_de_prueba() -> Iterator[Session]:
        yield session

    app.dependency_overrides[sesion] = _sesion_de_prueba
    yield TestClient(app)  # sin context manager: no corre el lifespan (siembra real)
