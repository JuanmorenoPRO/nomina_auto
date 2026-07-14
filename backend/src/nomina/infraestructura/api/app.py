"""Aplicación FastAPI.

Ejecutar en desarrollo:
    uv run uvicorn nomina.infraestructura.api.app:crear_app --factory --reload
"""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import inspect

from nomina.aplicacion.errores import NoEncontradoError, ReglaDeNegocioError
from nomina.infraestructura.api.rutas import router
from nomina.infraestructura.config import settings


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

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings().cors_origins.split(","),
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.exception_handler(NoEncontradoError)
    async def _no_encontrado(_: Request, exc: NoEncontradoError) -> JSONResponse:
        return JSONResponse(status_code=404, content={"detail": str(exc)})

    @app.exception_handler(ReglaDeNegocioError)
    async def _regla_negocio(_: Request, exc: ReglaDeNegocioError) -> JSONResponse:
        return JSONResponse(status_code=409, content={"detail": str(exc)})

    @app.exception_handler(ValueError)
    async def _valor_invalido(_: Request, exc: ValueError) -> JSONResponse:
        return JSONResponse(status_code=400, content={"detail": str(exc)})

    app.include_router(router)
    return app
