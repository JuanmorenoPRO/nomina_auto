"""Parámetros legales de referencia para poblar la configuración inicial.

⚠️ VERIFICAR contra fuente oficial antes de producción. En Fase 2 estos valores
se siembran en la tabla `parametro_legal` y se administran desde la UI; el motor
nunca los conoce: siempre recibe un ProveedorParametros.
"""

from __future__ import annotations

from datetime import date

from nomina.dominio.entidades.parametro_legal import ConjuntoParametros, ParametroLegal
from nomina.dominio.valores.vigencia import Vigencia


def _p(codigo: str, valor: str, desde: date, hasta: date | None = None, norma: str = "") -> ParametroLegal:
    return ParametroLegal(codigo=codigo, valor=valor, vigencia=Vigencia(desde, hasta), norma=norma)


PARAMETROS_SEMILLA: tuple[ParametroLegal, ...] = (
    # Jornada nocturna: 21:00 hasta la Ley 2466/2025, 19:00 desde el 25-dic-2025
    _p("jornada_nocturna_inicio", "21:00", date(2000, 1, 1), date(2025, 12, 24), "Ley 1846/2017"),
    _p("jornada_nocturna_inicio", "19:00", date(2025, 12, 25), None, "Ley 2466/2025"),
    _p("jornada_nocturna_fin", "06:00", date(2000, 1, 1), None, "CST art. 160"),
    _p("recargo_nocturno", "0.35", date(2000, 1, 1), None, "CST art. 168"),
    _p("extra_diurna", "0.25", date(2000, 1, 1), None, "CST art. 168"),
    _p("extra_nocturna", "0.75", date(2000, 1, 1), None, "CST art. 168"),
    # Recargo dominical/festivo escalonado por la Ley 2466/2025
    _p("recargo_dominical_festivo", "0.75", date(2000, 1, 1), date(2025, 6, 30), "CST art. 179"),
    _p("recargo_dominical_festivo", "0.80", date(2025, 7, 1), date(2026, 6, 30), "Ley 2466/2025"),
    _p("recargo_dominical_festivo", "0.90", date(2026, 7, 1), date(2027, 6, 30), "Ley 2466/2025"),
    _p("recargo_dominical_festivo", "1.00", date(2027, 7, 1), None, "Ley 2466/2025"),
    # Reducción escalonada de la jornada máxima semanal, Ley 2101/2021
    _p("jornada_maxima_semanal", "46", date(2023, 7, 15), date(2024, 7, 14), "Ley 2101/2021"),
    _p("jornada_maxima_semanal", "45", date(2024, 7, 15), date(2025, 7, 14), "Ley 2101/2021"),
    _p("jornada_maxima_semanal", "44", date(2025, 7, 15), date(2026, 7, 14), "Ley 2101/2021"),
    _p("jornada_maxima_semanal", "42", date(2026, 7, 15), None, "Ley 2101/2021"),
    _p("horas_quincena", "110", date(2000, 1, 1), None, "práctica actual (contadora)"),
    _p("divisor_hora_ordinaria", "220", date(2000, 1, 1), None, "220 h/mes (planilla contadora)"),
    _p("tope_horas_extra_dia", "2", date(2000, 1, 1), None, "Ley 6ª/1981 art. 1"),
    _p("horas_jornada_diaria", "8", date(2000, 1, 1), None, "jornada diaria (umbral estrategia 'diaria')"),
    # Aportes del empleado a seguridad social (se descuentan solo en unidades marcadas)
    _p("aporte_salud_empleado", "0.04", date(2000, 1, 1), None, "Ley 100/1993 art. 204"),
    _p("aporte_pension_empleado", "0.04", date(2000, 1, 1), None, "Ley 100/1993 art. 20"),
    # Auxilio de transporte (mensual) — verificar decreto de cada año
    _p("auxilio_transporte_mensual", "200000", date(2025, 1, 1), date(2025, 12, 31), "Dec. 1573/2024"),
    _p("auxilio_transporte_mensual", "249095", date(2026, 1, 1), None, "planilla contadora 2026"),
    _p("estrategia_clasificacion_extras", "presupuesto_quincenal", date(2000, 1, 1), None,
       "decisión de negocio: método actual de la contadora"),
)


def parametros_semilla() -> ConjuntoParametros:
    return ConjuntoParametros(parametros=PARAMETROS_SEMILLA)
