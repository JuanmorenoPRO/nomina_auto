"""Zona horaria de negocio: toda fecha/hora de turnos vive en America/Bogota."""

from zoneinfo import ZoneInfo

BOGOTA = ZoneInfo("America/Bogota")

MINUTOS_POR_HORA = 60
