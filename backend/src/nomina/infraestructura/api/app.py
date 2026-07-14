"""Aplicación FastAPI con endurecimiento de seguridad.

Ejecutar en desarrollo:
    uv run uvicorn nomina.infraestructura.api.app:crear_app --factory --reload --port 8001
"""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import inspect

from nomina.aplicacion.errores import NoEncontradoError, ReglaDeNegocioError
from nomina.infraestructura.api.rutas import router
from nomina.infraestructura.api.rutas_auth import router as router_auth
from nomina.infraestructura.config import settings
from nomina.infraestructura.seguridad.auth import (
    CredencialesInvalidasError,
    DemasiadosIntentosError,
    LimitadorDeIntentos,
)


@asynccontextmanager
async def _ciclo_de_vida(app: FastAPI):
    # siembra de parámetros si la BD ya está migrada y la tabla está vacía
    from nomina.infraestructura.persistencia.base import crear_engine, fabrica_sesiones
    from nomina.infraestructura.persistencia.sembrar import sembrar_parametros

    engine = crear_engine()
    if inspect(engine).has_table("parametro_legal"):
        with fabrica_sesiones(engine)() as session:
            sembrar_parametros(session)
            session.commit()
    yield


def crear_app() -> FastAPI:
    app = FastAPI(title="Nómina Unidades Residenciales", lifespan=_ciclo_de_vida)
    app.state.limitador_login = LimitadorDeIntentos()

    # CORS restrictivo: solo los orígenes configurados y lo mínimo necesario
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[o.strip() for o in settings().cors_origins.split(",") if o.strip()],
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "DELETE"],
        allow_headers=["Content-Type"],
    )

    @app.middleware("http")
    async def cabeceras_de_seguridad(request: Request, siguiente):
        respuesta = await siguiente(request)
        respuesta.headers["X-Content-Type-Options"] = "nosniff"
        respuesta.headers["X-Frame-Options"] = "DENY"
        respuesta.headers["Referrer-Policy"] = "no-referrer"
        respuesta.headers["Cache-Control"] = "no-store"
        if settings().cookie_segura:  # producción (HTTPS)
            respuesta.headers["Strict-Transport-Security"] = "max-age=63072000"
        return respuesta

    @app.exception_handler(NoEncontradoError)
    async def _no_encontrado(_: Request, exc: NoEncontradoError) -> JSONResponse:
        return JSONResponse(status_code=404, content={"detail": str(exc)})

    @app.exception_handler(ReglaDeNegocioError)
    async def _regla_negocio(_: Request, exc: ReglaDeNegocioError) -> JSONResponse:
        return JSONResponse(status_code=409, content={"detail": str(exc)})

    @app.exception_handler(CredencialesInvalidasError)
    async def _credenciales(_: Request, exc: CredencialesInvalidasError) -> JSONResponse:
        return JSONResponse(status_code=401, content={"detail": str(exc)})

    @app.exception_handler(DemasiadosIntentosError)
    async def _rate_limit(_: Request, exc: DemasiadosIntentosError) -> JSONResponse:
        return JSONResponse(status_code=429, content={"detail": str(exc)})

    @app.exception_handler(ValueError)
    async def _valor_invalido(_: Request, exc: ValueError) -> JSONResponse:
        return JSONResponse(status_code=400, content={"detail": str(exc)})

    app.include_router(router_auth)
    app.include_router(router)
    return app
