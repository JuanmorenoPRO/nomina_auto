"""Validaciones del dominio: entradas imposibles se rechazan con error claro."""

from datetime import date, time

import pytest

from nomina.dominio.entidades.parametro_legal import (
    ConjuntoParametros,
    ParametroLegal,
    ParametroNoVigenteError,
)
from nomina.dominio.entidades.turno import Turno, validar_sin_solapamientos
from nomina.dominio.servicios.clasificador_extras import clasificar_extras
from nomina.dominio.valores.vigencia import Vigencia
from nomina.semilla import parametros_semilla


def test_turnos_solapados_se_rechazan():
    turnos = [
        Turno(date(2026, 3, 2), time(6, 0), time(18, 0)),
        Turno(date(2026, 3, 2), time(17, 0), time(23, 0)),
    ]
    with pytest.raises(ValueError, match="solapados"):
        validar_sin_solapamientos(turnos)


def test_turno_que_cruza_medianoche_no_solapa_con_el_siguiente():
    turnos = [
        Turno(date(2026, 3, 2), time(18, 0), time(6, 0)),
        Turno(date(2026, 3, 3), time(6, 0), time(14, 0)),
    ]
    validar_sin_solapamientos(turnos)  # contiguos, no solapados


def test_vigencia_invalida():
    with pytest.raises(ValueError, match="Vigencia inválida"):
        Vigencia(desde=date(2026, 1, 1), hasta=date(2025, 1, 1))


def test_vigencias_solapadas_del_mismo_parametro_se_rechazan():
    with pytest.raises(ValueError, match="solapadas"):
        ConjuntoParametros(
            parametros=(
                ParametroLegal("recargo_nocturno", "0.35", Vigencia(date(2025, 1, 1))),
                ParametroLegal("recargo_nocturno", "0.40", Vigencia(date(2026, 1, 1))),
            )
        )


def test_parametro_sin_vigencia_para_la_fecha():
    parametros = ConjuntoParametros(
        parametros=(
            ParametroLegal("recargo_nocturno", "0.35", Vigencia(date(2026, 1, 1))),
        )
    )
    with pytest.raises(ParametroNoVigenteError, match="recargo_nocturno"):
        parametros.valor("recargo_nocturno", date(2025, 6, 1))


def test_estrategia_desconocida_se_rechaza():
    with pytest.raises(ValueError, match="desconocida"):
        clasificar_extras([], parametros_semilla(), date(2026, 1, 1), "inventada")
