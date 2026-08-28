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
    # Reducción escalonada de la jornada máxima semanal, Ley 2101/2021:
    # 47 h (15-jul-2023), 46 h (15-jul-2024), 44 h (15-jul-2025), 42 h (15-jul-2026).
    _p("jornada_maxima_semanal", "47", date(2023, 7, 15), date(2024, 7, 14), "Ley 2101/2021"),
    _p("jornada_maxima_semanal", "46", date(2024, 7, 15), date(2025, 7, 14), "Ley 2101/2021"),
    _p("jornada_maxima_semanal", "44", date(2025, 7, 15), date(2026, 7, 14), "Ley 2101/2021"),
    _p("jornada_maxima_semanal", "42", date(2026, 7, 15), None, "Ley 2101/2021"),
    # Horas ordinarias de la quincena y divisor de mensualización: bajan con la reducción
    # de la jornada máxima a 42 h/semana (Ley 2101/2021) el 15-jul-2026: 220→210 h/mes.
    _p("horas_quincena", "110", date(2000, 1, 1), date(2026, 7, 14), "práctica contadora (jornada 44 h)"),
    _p("horas_quincena", "105", date(2026, 7, 15), None, "práctica contadora (jornada 42 h, Ley 2101/2021)"),
    _p("divisor_hora_ordinaria", "220", date(2000, 1, 1), date(2026, 7, 14), "220 h/mes (jornada 44 h)"),
    _p("divisor_hora_ordinaria", "210", date(2026, 7, 15), None, "210 h/mes (jornada 42 h, Ley 2101/2021)"),
    _p("tope_horas_extra_dia", "2", date(2000, 1, 1), None, "Ley 6ª/1981 art. 1"),
    _p("horas_jornada_diaria", "8", date(2000, 1, 1), None, "jornada diaria (umbral estrategia 'diaria')"),
    # Aportes del empleado a seguridad social (se descuentan solo en unidades marcadas)
    _p("aporte_salud_empleado", "0.04", date(2000, 1, 1), None, "Ley 100/1993 art. 204"),
    _p("aporte_pension_empleado", "0.04", date(2000, 1, 1), None, "Ley 100/1993 art. 20"),
    # Auxilio de transporte (mensual) — verificar decreto de cada año
    _p("auxilio_transporte_mensual", "200000", date(2025, 1, 1), date(2025, 12, 31), "Dec. 1573/2024"),
    _p("auxilio_transporte_mensual", "249095", date(2026, 1, 1), None, "planilla contadora 2026"),
    # Estrategia por defecto para unidades sin `config.estrategia_extras` propio.
    # Hasta el 14-jul-2026, el método de la contadora (presupuesto de la quincena).
    # Desde el 15-jul-2026 el criterio legal: trabajo suplementario es el que excede
    # la jornada ordinaria — 8 h/día y 42 h/semana (CST art. 159 y 161, Ley 2101/2021).
    # Un presupuesto quincenal/mensual de horas no es un tope de jornada: el divisor
    # (210 h = 42/6 × 30, Concepto MinTrabajo 16177 de 2023) solo sirve para hallar el
    # valor de la hora ordinaria.
    _p("estrategia_clasificacion_extras", "presupuesto_quincenal", date(2000, 1, 1),
       date(2026, 7, 14), "decisión de negocio: método de la contadora"),
    _p("estrategia_clasificacion_extras", "semanal_legal", date(2026, 7, 15), None,
       "CST art. 159 y 161; Ley 2101/2021"),
    # Tasas para apropiaciones de seguridad social (segunda quincena)
    _p("aprop_sena", "0.02", date(2000, 1, 1), None, "Ley 21/1982 art. 7"),
    _p("aprop_icbf", "0.03", date(2000, 1, 1), None, "Ley 89/1988 art. 1"),
    _p("aprop_caja_compensacion", "0.04", date(2000, 1, 1), None, "Ley 21/1982 art. 7"),
    _p("aprop_salud_total", "0.125", date(2000, 1, 1), None, "Ley 100/1993 art. 204 (8.5% empleador + 4% empleado)"),
    _p("aprop_pension_total", "0.16", date(2000, 1, 1), None, "Ley 100/1993 art. 20 (12% empleador + 4% empleado)"),
    _p("aprop_arl", "0.01044", date(2000, 1, 1), None, "Decreto 1607/2002 (riesgo I)"),
    _p("aprop_vacaciones", "0.0417", date(2000, 1, 1), None, "CST art. 186 (15 días/año)"),
    _p("aprop_prima", "0.0833", date(2000, 1, 1), None, "CST art. 306 (1 mes/año)"),
    _p("aprop_cesantias", "0.0833", date(2000, 1, 1), None, "Ley 50/1990 art. 99"),
    _p("aprop_intereses_cesantias", "0.12", date(2000, 1, 1), None, "Ley 52/1975 art. 1"),
)


def parametros_semilla() -> ConjuntoParametros:
    return ConjuntoParametros(parametros=PARAMETROS_SEMILLA)
