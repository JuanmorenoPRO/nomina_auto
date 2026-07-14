from collections.abc import Iterator

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from nomina.dominio.entidades.usuario import Rol
from nomina.infraestructura.api.app import crear_app
from nomina.infraestructura.persistencia.base import Base, fabrica_sesiones, sesion
from nomina.infraestructura.persistencia.modelos import UsuarioModel
from nomina.infraestructura.persistencia.sembrar import sembrar_parametros
from nomina.infraestructura.seguridad.contrasenas import hashear

CONTRASENA_PRUEBA = "clave-de-prueba-123"
# Argon2id es deliberadamente costoso: hashear UNA vez para toda la corrida.
_HASH_PRUEBA = hashear(CONTRASENA_PRUEBA)

USUARIOS_PRUEBA = {
    Rol.ADMIN: "admin@prueba.co",
    Rol.CONTADORA: "contadora@prueba.co",
    Rol.OPERADOR: "operador@prueba.co",
}


@pytest.fixture
def session() -> Iterator[Session]:
    """BD SQLite en memoria: migrada, sembrada, con triggers y usuarios de prueba."""
    engine = create_engine(
        "sqlite://", poolclass=StaticPool, connect_args={"check_same_thread": False}
    )
    Base.metadata.create_all(engine)
    with engine.begin() as conn:  # mismos triggers append-only de la migración
        conn.execute(text(
            "CREATE TRIGGER auditoria_sin_update BEFORE UPDATE ON auditoria "
            "BEGIN SELECT RAISE(ABORT, 'auditoria es append-only'); END"
        ))
        conn.execute(text(
            "CREATE TRIGGER auditoria_sin_delete BEFORE DELETE ON auditoria "
            "BEGIN SELECT RAISE(ABORT, 'auditoria es append-only'); END"
        ))
    with fabrica_sesiones(engine)() as s:
        sembrar_parametros(s)
        for rol, email in USUARIOS_PRUEBA.items():
            s.add(UsuarioModel(email=email, hash_password=_HASH_PRUEBA, rol=rol.value))
        s.commit()
        yield s


@pytest.fixture
def app_prueba(session: Session) -> FastAPI:
    app = crear_app()

    def _sesion_de_prueba() -> Iterator[Session]:
        yield session

    app.dependency_overrides[sesion] = _sesion_de_prueba
    return app


def _cliente_autenticado(app: FastAPI, rol: Rol) -> TestClient:
    cliente = TestClient(app)  # sin context manager: no corre el lifespan
    r = cliente.post(
        "/auth/login",
        json={"email": USUARIOS_PRUEBA[rol], "contrasena": CONTRASENA_PRUEBA},
    )
    assert r.status_code == 200, r.text
    return cliente


@pytest.fixture
def client(app_prueba: FastAPI) -> TestClient:
    """Cliente admin: puede ejercitar cualquier endpoint (tests funcionales)."""
    return _cliente_autenticado(app_prueba, Rol.ADMIN)


@pytest.fixture
def client_contadora(app_prueba: FastAPI) -> TestClient:
    return _cliente_autenticado(app_prueba, Rol.CONTADORA)


@pytest.fixture
def client_operador(app_prueba: FastAPI) -> TestClient:
    return _cliente_autenticado(app_prueba, Rol.OPERADOR)


@pytest.fixture
def client_anonimo(app_prueba: FastAPI) -> TestClient:
    return TestClient(app_prueba)
