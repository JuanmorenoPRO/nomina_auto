"""Golden test de EDIFICIO LORENA P.H — HERNAN 1-15 de agosto de 2026.

Reproduce la hoja real `AGOSTO 2026 LORENA.xlsx` del empleado que solo trabajó parte
de la quincena. Es el caso que definió la regla de «liquidar sobre lo trabajado»:

- La contadora liquida **49 h de TIEMPO ORDINARIO** = todas las horas laboradas,
  con las 14 h festivas incluidas — no solo las de día ordinario.
- Encima paga TIEMPO FESTIVO con su factor completo (×1.90).
- El auxilio va en proporción a lo laborado: `mensual × 49 / 210` = $58.122,
  que es lo mismo que su `mensual/30 × 7 días` con jornada de 7 h.

Diferencia DOCUMENTADA: la hoja clasifica el día 7 (viernes 7-ago, Batalla de Boyacá)
como 7 h ordinarias + 7 h festivas. El motor lo trata entero como festivo, porque el
día es festivo por ley, y con la estrategia `jornada` (umbral 8 h) parte el turno
doble en extras. Por eso aquí se fija solo lo que la regla nueva determina —la base
del ordinario y el auxilio—, que no depende de ese reparto: da 49 h en ambos casos.
"""

from datetime import date, time
from decimal import Decimal

from nomina.dominio.entidades.turno import Turno
from nomina.dominio.servicios.calculadora import liquidar
from nomina.dominio.servicios.calendario_festivos import CalendarioFestivos
from nomina.dominio.servicios.clasificador_extras import clasificar_extras
from nomina.dominio.servicios.segmentador import segmentar_turnos

PARAMETROS_FECHA = date(2026, 8, 1)
SALARIO = Decimal(1_750_905)  # salario mínimo 2026, hoja de HERNAN DARIO PALACIO


def _liquidacion(parametros):
    """Turnos de Hernán: domingo 2 (7 h), días 3–6 (7 h c/u) y el 7 con turno doble."""
    turnos = [Turno(date(2026, 8, 2), time(6), time(13))]
    turnos += [Turno(date(2026, 8, d), time(6), time(13)) for d in (3, 4, 5, 6)]
    turnos += [
        Turno(date(2026, 8, 7), time(6), time(13)),
        Turno(date(2026, 8, 7), time(14), time(21)),
    ]
    tramos = segmentar_turnos(turnos, parametros, CalendarioFestivos())
    clasificados = clasificar_extras(
        tramos, parametros, PARAMETROS_FECHA, estrategia="jornada"
    )
    return liquidar(
        clasificados,
        SALARIO,
        parametros,
        PARAMETROS_FECHA,
        incluir_auxilio_transporte=True,
        auxilio_prorrateado=True,
        quincena_completa=False,
    )


def _valor(liq, codigo: str) -> Decimal:
    return sum((c.valor for c in liq.conceptos if c.codigo == codigo), Decimal(0))


def test_tarifa_hora_coincide_con_la_hoja():
    from nomina.semilla import parametros_semilla

    parametros = parametros_semilla()
    tarifa = SALARIO / parametros.divisor_hora_ordinaria(PARAMETROS_FECHA)
    # La hoja calcula 8337.642857142857 (divisor 210, jornada 42 h)
    assert tarifa.quantize(Decimal("0.000001")) == Decimal("8337.642857")


def test_tiempo_ordinario_son_las_49_horas_laboradas():
    """La hoja liquida 49 h por $408.544,5: TODAS las horas, festivas incluidas."""
    from nomina.semilla import parametros_semilla

    liq = _liquidacion(parametros_semilla())
    ordinario = next(c for c in liq.conceptos if c.codigo == "tiempo_ordinario")
    assert ordinario.horas == Decimal(49)
    # La hoja deja 408.544,5 sin redondear; el motor redondea a peso con
    # ROUND_HALF_UP una sola vez al final, así que sube medio peso.
    assert ordinario.valor == Decimal(408_545)


def test_auxilio_en_proporcion_a_lo_laborado():
    """La hoja paga $58.122,17 = 249.095/30 × 7 días = 249.095 × 49 / 210."""
    from nomina.semilla import parametros_semilla

    liq = _liquidacion(parametros_semilla())
    auxilio = next(c for c in liq.conceptos if c.codigo == "auxilio_transporte")
    assert auxilio.componentes == {"horas_laboradas": Decimal(49)}
    assert auxilio.valor == Decimal(58_122)


def test_las_horas_festivas_no_se_pierden():
    """El domingo 2 y el festivo del 7 se reconocen como festivos, aparte del
    ordinario: es justo lo que el usuario reportó que faltaba."""
    from nomina.semilla import parametros_semilla

    liq = _liquidacion(parametros_semilla())
    festivas = _valor(liq, "festivo_diurno") + _valor(liq, "extra_diurna_festiva")
    assert festivas > 0
    # Y la base del ordinario no las excluye: 49 h = 35 ordinarias + 14 festivas.
    assert _valor(liq, "tiempo_ordinario") == Decimal(408_545)
