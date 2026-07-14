"""Autenticación por sesiones y autorización por roles.

- Sesiones con expiración; en BD se guarda el SHA-256 del token, nunca el token.
- La cookie es HttpOnly + SameSite=Lax (Secure según configuración).
- Los permisos se verifican SIEMPRE en el backend, nunca solo en la UI.
"""

from __future__ import annotations

import hashlib
import secrets
import time
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Annotated
from uuid import UUID

from fastapi import Depends, HTTPException, Request
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from nomina.dominio.entidades.usuario import Rol, Usuario
from nomina.infraestructura.config import settings
from nomina.infraestructura.persistencia.base import sesion
from nomina.infraestructura.persistencia.modelos import SesionModel, UsuarioModel
from nomina.infraestructura.seguridad.contrasenas import hashear, verificar

COOKIE_SESION = "sesion"


class CredencialesInvalidasError(Exception):
    """Usuario o contraseña incorrectos (→ 401, mensaje genérico)."""


class DemasiadosIntentosError(Exception):
    """Rate limit de login superado (→ 429)."""


@dataclass
class LimitadorDeIntentos:
    """Limita intentos fallidos de login por clave (IP) en una ventana móvil."""

    max_intentos: int = 5
    ventana_segundos: int = 60
    _fallos: dict[str, list[float]] = field(default_factory=dict)

    def verificar(self, clave: str) -> None:
        ahora = time.monotonic()
        recientes = [t for t in self._fallos.get(clave, []) if ahora - t < self.ventana_segundos]
        self._fallos[clave] = recientes
        if len(recientes) >= self.max_intentos:
            raise DemasiadosIntentosError(
                f"Demasiados intentos fallidos; espere {self.ventana_segundos} segundos"
            )

    def registrar_fallo(self, clave: str) -> None:
        self._fallos.setdefault(clave, []).append(time.monotonic())

    def limpiar(self, clave: str) -> None:
        self._fallos.pop(clave, None)


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def _a_dominio(m: UsuarioModel) -> Usuario:
    return Usuario(id=m.id, email=m.email, rol=Rol(m.rol), activo=m.activo)


def crear_usuario(
    session: Session, email: str, contrasena: str, rol: Rol, activo: bool = True
) -> Usuario:
    modelo = UsuarioModel(
        email=email.strip().lower(),
        hash_password=hashear(contrasena),
        rol=rol.value,
        activo=activo,
    )
    session.add(modelo)
    session.flush()
    return _a_dominio(modelo)


def listar_usuarios(session: Session) -> list[Usuario]:
    filas = session.scalars(select(UsuarioModel).order_by(UsuarioModel.email))
    return [_a_dominio(m) for m in filas]


def iniciar_sesion(session: Session, email: str, contrasena: str) -> tuple[Usuario, str]:
    """Valida credenciales y crea una sesión. Devuelve (usuario, token para cookie)."""
    modelo = session.scalars(
        select(UsuarioModel).where(UsuarioModel.email == email.strip().lower())
    ).first()
    # mensaje idéntico exista o no el usuario: no revelar cuáles emails existen
    if modelo is None or not modelo.activo or not verificar(modelo.hash_password, contrasena):
        raise CredencialesInvalidasError("Usuario o contraseña incorrectos")

    token = secrets.token_urlsafe(32)
    expira = datetime.now(UTC) + timedelta(hours=settings().duracion_sesion_horas)
    session.add(SesionModel(token_hash=_hash_token(token), usuario_id=modelo.id, expira_en=expira))
    session.flush()
    return _a_dominio(modelo), token


def cerrar_sesion(session: Session, token: str) -> None:
    session.execute(delete(SesionModel).where(SesionModel.token_hash == _hash_token(token)))
    session.flush()


def usuario_de_token(session: Session, token: str) -> Usuario | None:
    fila = session.scalars(
        select(SesionModel).where(SesionModel.token_hash == _hash_token(token))
    ).first()
    if fila is None:
        return None
    expira = fila.expira_en if fila.expira_en.tzinfo else fila.expira_en.replace(tzinfo=UTC)
    if expira < datetime.now(UTC):
        session.delete(fila)
        session.flush()
        return None
    modelo = session.get(UsuarioModel, fila.usuario_id)
    if modelo is None or not modelo.activo:
        return None
    return _a_dominio(modelo)


def usuario_actual(request: Request, session: Annotated[Session, Depends(sesion)]) -> Usuario:
    token = request.cookies.get(COOKIE_SESION)
    usuario = usuario_de_token(session, token) if token else None
    if usuario is None:
        raise HTTPException(status_code=401, detail="No autenticado")
    return usuario


def requiere(rol_minimo: Rol):
    def dependencia(usuario: Annotated[Usuario, Depends(usuario_actual)]) -> Usuario:
        if not usuario.rol.al_menos(rol_minimo):
            raise HTTPException(
                status_code=403,
                detail=f"Se requiere rol {rol_minimo.value} o superior",
            )
        return usuario

    return dependencia


UsuarioOperador = Annotated[Usuario, Depends(requiere(Rol.OPERADOR))]
UsuarioContadora = Annotated[Usuario, Depends(requiere(Rol.CONTADORA))]
UsuarioAdmin = Annotated[Usuario, Depends(requiere(Rol.ADMIN))]


def desactivar_usuario(session: Session, usuario_id: UUID) -> Usuario | None:
    modelo = session.get(UsuarioModel, usuario_id)
    if modelo is None:
        return None
    modelo.activo = False
    session.execute(delete(SesionModel).where(SesionModel.usuario_id == usuario_id))
    session.flush()
    return _a_dominio(modelo)
