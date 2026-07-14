"""Errores de aplicación: la API los traduce a códigos HTTP."""


class NoEncontradoError(LookupError):
    """El recurso pedido no existe (→ 404)."""


class ReglaDeNegocioError(ValueError):
    """La operación viola una regla de negocio (→ 409)."""
