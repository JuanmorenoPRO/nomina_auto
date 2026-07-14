"""Crea el primer usuario administrador (bootstrap).

Uso:
    NOMINA_ADMIN_PASSWORD='...' uv run python -m nomina.infraestructura.seguridad.crear_admin --email admin@ejemplo.com

Si no está la variable de entorno, la contraseña se pide por consola (getpass):
nunca va en argumentos de línea de comandos ni en el código.
"""

from __future__ import annotations

import argparse
import getpass
import os

from sqlalchemy import select

from nomina.dominio.entidades.usuario import Rol
from nomina.infraestructura.persistencia.base import crear_engine, fabrica_sesiones
from nomina.infraestructura.persistencia.modelos import UsuarioModel
from nomina.infraestructura.seguridad.auth import crear_usuario


def main() -> None:
    parser = argparse.ArgumentParser(description="Crear usuario administrador")
    parser.add_argument("--email", required=True)
    parser.add_argument("--rol", choices=[r.value for r in Rol], default=Rol.ADMIN.value)
    args = parser.parse_args()

    contrasena = os.environ.get("NOMINA_ADMIN_PASSWORD") or getpass.getpass("Contraseña: ")
    if len(contrasena) < 10:
        raise SystemExit("La contraseña debe tener al menos 10 caracteres")

    engine = crear_engine()
    with fabrica_sesiones(engine)() as session:
        existente = session.scalars(
            select(UsuarioModel).where(UsuarioModel.email == args.email.strip().lower())
        ).first()
        if existente is not None:
            raise SystemExit(f"Ya existe un usuario con email {args.email}")
        usuario = crear_usuario(session, args.email, contrasena, Rol(args.rol))
        session.commit()
    print(f"Usuario creado: {usuario.email} ({usuario.rol.value})")


if __name__ == "__main__":
    main()
