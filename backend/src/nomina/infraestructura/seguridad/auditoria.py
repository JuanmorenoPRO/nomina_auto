"""Registro de auditoría (RF7). La tabla es append-only por triggers de BD."""

from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from nomina.infraestructura.persistencia.modelos import AuditoriaModel


def auditar(
    session: Session,
    usuario_email: str,
    accion: str,
    entidad: str,
    entidad_id: str = "",
    antes: dict[str, Any] | None = None,
    despues: dict[str, Any] | None = None,
) -> None:
    session.add(
        AuditoriaModel(
            usuario_email=usuario_email,
            accion=accion,
            entidad=entidad,
            entidad_id=str(entidad_id),
            antes=antes,
            despues=despues,
        )
    )
    session.flush()


def ultimos_registros(session: Session, limite: int = 200) -> list[AuditoriaModel]:
    return list(
        session.scalars(
            select(AuditoriaModel).order_by(AuditoriaModel.timestamp.desc()).limit(limite)
        )
    )
