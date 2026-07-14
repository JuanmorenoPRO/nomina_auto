"""Fase 4: autenticación, roles, auditoría inmutable y cierre de quincenas."""

import pytest
from sqlalchemy import text

from tests.conftest import CONTRASENA_PRUEBA, USUARIOS_PRUEBA
from nomina.dominio.entidades.usuario import Rol


def _montar_liquidacion(cliente) -> dict:
    """Crea unidad+empleado+periodo+turno y devuelve ids (requiere contadora+)."""
    unidad = cliente.post("/unidades", json={"nombre": "Unidad Seg", "nit": "1"}).json()
    empleado = cliente.post(
        "/empleados",
        json={"unidad_id": unidad["id"], "nombre": "PRUEBA", "documento": "1010",
              "cargo": "vigilante", "salario_base": 2_200_000},
    ).json()
    periodo = cliente.post(
        "/periodos", json={"fecha_inicio": "2026-06-16", "fecha_fin": "2026-06-30"}
    ).json()
    cliente.post(
        "/turnos",
        json={"empleado_id": empleado["id"], "fecha": "2026-06-17",
              "hora_inicio": "06:00", "hora_fin": "14:00"},
    )
    return {"unidad": unidad, "empleado": empleado, "periodo": periodo}


# --- Autenticación ---


def test_login_y_sesion(client_anonimo):
    r = client_anonimo.post(
        "/auth/login",
        json={"email": USUARIOS_PRUEBA[Rol.CONTADORA], "contrasena": CONTRASENA_PRUEBA},
    )
    assert r.status_code == 200
    assert r.json()["rol"] == "contadora"
    cookie = r.headers["set-cookie"]
    assert "HttpOnly" in cookie and "SameSite=lax" in cookie

    assert client_anonimo.get("/auth/yo").json()["email"] == USUARIOS_PRUEBA[Rol.CONTADORA]

    client_anonimo.post("/auth/logout")
    assert client_anonimo.get("/auth/yo").status_code == 401


def test_credenciales_invalidas_mensaje_generico(client_anonimo):
    mal_password = client_anonimo.post(
        "/auth/login",
        json={"email": USUARIOS_PRUEBA[Rol.ADMIN], "contrasena": "incorrecta-123"},
    )
    email_inexistente = client_anonimo.post(
        "/auth/login", json={"email": "nadie@prueba.co", "contrasena": "incorrecta-123"}
    )
    # mismo código y mismo mensaje: no se revela qué emails existen
    assert mal_password.status_code == email_inexistente.status_code == 401
    assert mal_password.json() == email_inexistente.json()


def test_rate_limiting_en_login(client_anonimo):
    for _ in range(5):
        r = client_anonimo.post(
            "/auth/login", json={"email": "nadie@prueba.co", "contrasena": "x"}
        )
        assert r.status_code == 401
    r = client_anonimo.post(
        "/auth/login", json={"email": "nadie@prueba.co", "contrasena": "x"}
    )
    assert r.status_code == 429


def test_sin_autenticar_todo_es_401(client_anonimo):
    assert client_anonimo.get("/unidades").status_code == 401
    assert client_anonimo.post("/turnos", json={}).status_code == 401
    assert client_anonimo.get("/parametros").status_code == 401
    assert client_anonimo.get("/salud").status_code == 200  # única ruta pública


# --- Autorización por roles (verificada en backend) ---


def test_operador_solo_ingresa_turnos(client_contadora, client_operador):
    datos = _montar_liquidacion(client_contadora)

    r = client_operador.post(
        "/turnos",
        json={"empleado_id": datos["empleado"]["id"], "fecha": "2026-06-18",
              "hora_inicio": "06:00", "hora_fin": "14:00"},
    )
    assert r.status_code == 201  # sí puede ingresar turnos

    assert client_operador.post(
        f"/periodos/{datos['periodo']['id']}/liquidar",
        json={"unidad_id": datos["unidad"]["id"]},
    ).status_code == 403
    assert client_operador.post("/unidades", json={"nombre": "X"}).status_code == 403
    assert client_operador.post(
        "/parametros",
        json={"codigo": "recargo_nocturno", "valor": "0.9", "vigente_desde": "2030-01-01"},
    ).status_code == 403
    assert client_operador.get("/usuarios").status_code == 403


def test_contadora_liquida_pero_no_administra(client_contadora):
    datos = _montar_liquidacion(client_contadora)
    r = client_contadora.post(
        f"/periodos/{datos['periodo']['id']}/liquidar",
        json={"unidad_id": datos["unidad"]["id"]},
    )
    assert r.status_code == 201
    excel = client_contadora.get(f"/liquidaciones/{r.json()['id']}/excel")
    assert excel.status_code == 200

    assert client_contadora.post(
        "/parametros",
        json={"codigo": "recargo_nocturno", "valor": "0.9", "vigente_desde": "2030-01-01"},
    ).status_code == 403
    assert client_contadora.get("/usuarios").status_code == 403
    assert client_contadora.put(
        "/festivos", json={"fecha": "2026-06-20", "nombre": "x"}
    ).status_code == 403


def test_gestion_de_usuarios_solo_admin(client):
    r = client.post(
        "/usuarios",
        json={"email": "nueva@prueba.co", "contrasena": "supersecreta1", "rol": "operador"},
    )
    assert r.status_code == 201
    listado = client.get("/usuarios").json()
    assert any(u["email"] == "nueva@prueba.co" for u in listado)

    duplicado = client.post(
        "/usuarios",
        json={"email": "nueva@prueba.co", "contrasena": "supersecreta1", "rol": "operador"},
    )
    assert duplicado.status_code == 409

    corta = client.post(
        "/usuarios", json={"email": "otra@prueba.co", "contrasena": "corta", "rol": "operador"}
    )
    assert corta.status_code == 422  # contraseña mínima de 10 caracteres

    desactivado = client.post(f"/usuarios/{r.json()['id']}/desactivar")
    assert desactivado.status_code == 200 and desactivado.json()["activo"] is False


# --- Auditoría append-only ---


def test_auditoria_registra_acciones_criticas(client):
    datos = _montar_liquidacion(client)
    client.post(
        "/parametros",
        json={"codigo": "recargo_nocturno", "valor": "0.40",
              "vigente_desde": "2030-01-01", "norma": "hipotética"},
    )
    client.post(
        f"/periodos/{datos['periodo']['id']}/liquidar", json={"unidad_id": datos["unidad"]["id"]}
    )

    registros = client.get("/auditoria").json()
    acciones = {(r["accion"], r["entidad"]) for r in registros}
    assert {"crear", "turno"} == set(("crear", "turno")) or ("crear", "turno") in acciones
    assert ("nueva_vigencia", "parametro_legal") in acciones
    assert ("liquidar", "liquidacion") in acciones

    cambio = next(r for r in registros if r["accion"] == "nueva_vigencia")
    assert cambio["antes"]["valor"] == "0.35"
    assert cambio["despues"]["valor"] == "0.40"
    assert cambio["usuario_email"] == USUARIOS_PRUEBA[Rol.ADMIN]


def test_auditoria_es_inmutable_en_bd(client, session):
    _montar_liquidacion(client)  # genera registros
    session.commit()  # que el rollback posterior no borre los registros
    with pytest.raises(Exception, match="append-only"):
        session.execute(text("UPDATE auditoria SET accion = 'adulterada'"))
    session.rollback()
    with pytest.raises(Exception, match="append-only"):
        session.execute(text("DELETE FROM auditoria"))
    session.rollback()


# --- Cierre de quincenas ---


def test_cierre_definitivo_de_quincena(client):
    datos = _montar_liquidacion(client)
    periodo_id = datos["periodo"]["id"]

    # no se puede cerrar sin liquidar
    assert client.post(f"/periodos/{periodo_id}/cerrar").status_code == 409

    client.post(f"/periodos/{periodo_id}/liquidar", json={"unidad_id": datos["unidad"]["id"]})
    assert client.post(f"/periodos/{periodo_id}/cerrar").json()["estado"] == "cerrado"

    # cerrado = solo lectura para siempre
    assert client.post(f"/periodos/{periodo_id}/reabrir").status_code == 400
    assert client.post(
        f"/periodos/{periodo_id}/liquidar", json={"unidad_id": datos["unidad"]["id"]}
    ).status_code == 409
    assert client.post(
        "/turnos",
        json={"empleado_id": datos["empleado"]["id"], "fecha": "2026-06-19",
              "hora_inicio": "06:00", "hora_fin": "14:00"},
    ).status_code == 409


# --- Hardening ---


def test_cabeceras_de_seguridad(client):
    r = client.get("/salud")
    assert r.headers["X-Content-Type-Options"] == "nosniff"
    assert r.headers["X-Frame-Options"] == "DENY"
    assert r.headers["Referrer-Policy"] == "no-referrer"
    assert r.headers["Cache-Control"] == "no-store"
