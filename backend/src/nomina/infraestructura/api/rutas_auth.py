"""Autenticación y gestión de usuarios (solo admin)."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy.orm import Session

from nomina.dominio.entidades.usuario import Rol, Usuario
from nomina.infraestructura.config import settings
from nomina.infraestructura.persistencia.base import sesion
from nomina.infraestructura.seguridad.auditoria import auditar, ultimos_registros
from nomina.infraestructura.seguridad.auth import (
    COOKIE_SESION,
    UsuarioAdmin,
    cerrar_sesion,
    crear_usuario,
    desactivar_usuario,
    iniciar_sesion,
    listar_usuarios,
    usuario_actual,
)

Sesion = Annotated[Session, Depends(sesion)]

router = APIRouter()


class LoginSolicitud(BaseModel):
    email: EmailStr
    contrasena: str = Field(min_length=1, max_length=200)


class UsuarioRespuesta(BaseModel):
    id: UUID | None = None
    email: str
    rol: str
    activo: bool = True


class UsuarioCrear(BaseModel):
    email: EmailStr
    contrasena: str = Field(min_length=10, max_length=200)
    rol: Rol


class RegistroAuditoria(BaseModel):
    usuario_email: str
    accion: str
    entidad: str
    entidad_id: str
    antes: dict | None
    despues: dict | None
    timestamp: datetime


@router.post("/auth/login", response_model=UsuarioRespuesta)
def login(
    datos: LoginSolicitud, request: Request, respuesta: Response, session: Sesion
) -> UsuarioRespuesta:
    limitador = request.app.state.limitador_login
    clave = request.client.host if request.client else "desconocido"
    limitador.verificar(clave)
    try:
        usuario, token = iniciar_sesion(session, datos.email, datos.contrasena)
    except Exception:
        limitador.registrar_fallo(clave)
        raise
    limitador.limpiar(clave)
    respuesta.set_cookie(
        COOKIE_SESION,
        token,
        httponly=True,
        samesite="lax",
        secure=settings().cookie_segura,
        max_age=settings().duracion_sesion_horas * 3600,
    )
    return UsuarioRespuesta(id=usuario.id, email=usuario.email, rol=usuario.rol.value)


@router.post("/auth/logout", status_code=204)
def logout(request: Request, respuesta: Response, session: Sesion) -> None:
    token = request.cookies.get(COOKIE_SESION)
    if token:
        cerrar_sesion(session, token)
    respuesta.delete_cookie(COOKIE_SESION)


@router.get("/auth/yo", response_model=UsuarioRespuesta)
def yo(usuario: Annotated[Usuario, Depends(usuario_actual)]) -> UsuarioRespuesta:
    return UsuarioRespuesta(id=usuario.id, email=usuario.email, rol=usuario.rol.value)


@router.get("/usuarios", response_model=list[UsuarioRespuesta])
def usuarios(admin: UsuarioAdmin, session: Sesion) -> list[UsuarioRespuesta]:
    return [
        UsuarioRespuesta(id=u.id, email=u.email, rol=u.rol.value, activo=u.activo)
        for u in listar_usuarios(session)
    ]


@router.post("/usuarios", response_model=UsuarioRespuesta, status_code=201)
def crear(datos: UsuarioCrear, admin: UsuarioAdmin, session: Sesion) -> UsuarioRespuesta:
    if any(u.email == datos.email.lower() for u in listar_usuarios(session)):
        raise HTTPException(409, "Ya existe un usuario con ese email")
    usuario = crear_usuario(session, datos.email, datos.contrasena, datos.rol)
    auditar(session, admin.email, "crear", "usuario", str(usuario.id),
            despues={"email": usuario.email, "rol": usuario.rol.value})
    return UsuarioRespuesta(id=usuario.id, email=usuario.email, rol=usuario.rol.value)


@router.post("/usuarios/{usuario_id}/desactivar", response_model=UsuarioRespuesta)
def desactivar(usuario_id: UUID, admin: UsuarioAdmin, session: Sesion) -> UsuarioRespuesta:
    if usuario_id == admin.id:
        raise HTTPException(409, "No puede desactivarse a sí mismo")
    usuario = desactivar_usuario(session, usuario_id)
    if usuario is None:
        raise HTTPException(404, "No existe el usuario")
    auditar(session, admin.email, "desactivar", "usuario", str(usuario_id),
            antes={"activo": True}, despues={"activo": False})
    return UsuarioRespuesta(id=usuario.id, email=usuario.email, rol=usuario.rol.value,
                            activo=usuario.activo)


@router.get("/auditoria", response_model=list[RegistroAuditoria])
def auditoria(admin: UsuarioAdmin, session: Sesion, limite: int = 200) -> list[RegistroAuditoria]:
    return [
        RegistroAuditoria(
            usuario_email=r.usuario_email,
            accion=r.accion,
            entidad=r.entidad,
            entidad_id=r.entidad_id,
            antes=r.antes,
            despues=r.despues,
            timestamp=r.timestamp,
        )
        for r in ultimos_registros(session, min(limite, 1000))
    ]
