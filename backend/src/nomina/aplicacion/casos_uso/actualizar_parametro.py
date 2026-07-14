"""Caso de uso: crear una NUEVA VIGENCIA de un parámetro legal (RF5).

Nunca se edita un valor histórico: la vigencia abierta se cierra el día
anterior al inicio de la nueva. Las liquidaciones pasadas no se ven afectadas
porque el motor resuelve por fecha de tramo y cada liquidación guarda snapshot.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta

from nomina.aplicacion.errores import ReglaDeNegocioError
from nomina.dominio.entidades.parametro_legal import (
    CODIGOS_PARAMETROS,
    ConjuntoParametros,
    ParametroLegal,
)
from nomina.dominio.puertos.repositorios import RepositorioParametros
from nomina.dominio.valores.vigencia import Vigencia


@dataclass(frozen=True)
class ActualizarParametro:
    parametros: RepositorioParametros

    def ejecutar(
        self, codigo: str, valor: str, vigente_desde: date, norma: str = ""
    ) -> ParametroLegal:
        if codigo not in CODIGOS_PARAMETROS:
            raise ReglaDeNegocioError(f"Parámetro desconocido: '{codigo}'")

        existentes = [p for p in self.parametros.listar() if p.codigo == codigo]
        for p in existentes:
            if p.vigencia.desde >= vigente_desde:
                raise ReglaDeNegocioError(
                    f"Ya existe una vigencia de '{codigo}' que inicia el {p.vigencia.desde}; "
                    "la nueva debe iniciar después"
                )

        nuevo = ParametroLegal(
            codigo=codigo, valor=valor, vigencia=Vigencia(desde=vigente_desde), norma=norma
        )
        # validar el conjunto resultante ANTES de tocar la base
        cerrados = [
            ParametroLegal(
                codigo=p.codigo,
                valor=p.valor,
                vigencia=Vigencia(p.vigencia.desde, vigente_desde - timedelta(days=1)),
                norma=p.norma,
            )
            if p.vigencia.hasta is None
            else p
            for p in existentes
        ]
        otros = [p for p in self.parametros.listar() if p.codigo != codigo]
        ConjuntoParametros(parametros=tuple(otros + cerrados + [nuevo]))

        self.parametros.cerrar_vigencia_abierta(codigo, vigente_desde - timedelta(days=1))
        self.parametros.agregar(nuevo)
        return nuevo
