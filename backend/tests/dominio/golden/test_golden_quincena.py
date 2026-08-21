"""Golden tests: casos de aceptación con valores esperados calculados a mano.

Salario de referencia: $2.200.000/mes con divisor 220 → tarifa hora = $10.000
exactos, para que cada valor esperado sea verificable mentalmente.

Modelo de pago (planilla real de la contadora): el salario quincenal
(110 h × tarifa = salario/2) cubre las horas ordinarias; cada concepto paga lo
ADICIONAL. Aquí se verifica ese pago adicional por concepto.
"""

from datetime import date, time
from decimal import Decimal

from nomina.dominio.entidades.turno import Turno
from nomina.dominio.servicios.calculadora import liquidar
from nomina.dominio.servicios.calendario_festivos import CalendarioFestivos
from nomina.dominio.servicios.clasificador_extras import clasificar_extras
from nomina.dominio.servicios.segmentador import segmentar_turnos
from nomina.dominio.valores.tramo import TipoDia
from nomina.semilla import parametros_semilla

PARAMETROS = parametros_semilla()
CALENDARIO = CalendarioFestivos()
SALARIO = Decimal(2_200_000)  # tarifa = 10.000/h
BASE_QUINCENA = Decimal(1_100_000)  # 110 h × 10.000 = salario/2


def turno(fecha: str, inicio: str, fin: str, jornada_ordinaria_h: int | None = None) -> Turno:
    return Turno(
        date.fromisoformat(fecha),
        time.fromisoformat(inicio),
        time.fromisoformat(fin),
        minutos_jornada_ordinaria=None if jornada_ordinaria_h is None else jornada_ordinaria_h * 60,
    )


def liquidar_turnos(turnos, desde: str, estrategia: str | None = None):
    tramos = segmentar_turnos(turnos, PARAMETROS, CALENDARIO)
    clasificados = clasificar_extras(tramos, PARAMETROS, date.fromisoformat(desde), estrategia)
    return liquidar(
        clasificados, SALARIO, PARAMETROS, date.fromisoformat(desde),
        incluir_auxilio_transporte=False,
    )


def valor(liquidacion, codigo: str) -> Decimal:
    return sum((c.valor for c in liquidacion.conceptos if c.codigo == codigo), Decimal(0))


def adicional(liquidacion) -> Decimal:
    """Total devengado por encima del salario base de la quincena."""
    return liquidacion.total - valor(liquidacion, "tiempo_ordinario")


def test_1_turno_diurno_normal_entre_semana():
    """Lunes 06:00-14:00: 8 h diurnas ordinarias → ningún pago adicional."""
    liq = liquidar_turnos([turno("2026-03-02", "06:00", "14:00")], desde="2026-03-01")
    assert valor(liq, "tiempo_ordinario") == BASE_QUINCENA
    assert adicional(liq) == 0


def test_2_turno_nocturno_entre_semana():
    """Miércoles 18:00-06:00: recargo nocturno solo desde las 19:00.

    18-19 diurna (sin recargo) + 19-24 y 00-06 nocturnas = 11 h × 35% × 10.000.
    """
    liq = liquidar_turnos([turno("2026-03-04", "18:00", "06:00")], desde="2026-03-01")
    assert valor(liq, "recargo_nocturno") == Decimal(38_500)  # 11 h × 3.500
    assert adicional(liq) == Decimal(38_500)


def test_3_sabado_a_domingo_corte_en_medianoche():
    """Sábado 18:00 → domingo 06:00: el tramo tras las 00:00 es dominical.

    Sáb 18-19 diurna ordinaria: $0 · sáb 19-24 nocturna: 5 h × 0,35 = 17.500 ·
    dom 00-06 nocturna dominical: 6 h × (1 + 0,80 + 0,35) = 6 × 21.500 = 129.000.
    """
    liq = liquidar_turnos([turno("2026-03-07", "18:00", "06:00")], desde="2026-03-01")
    assert valor(liq, "recargo_nocturno") == Decimal(17_500)
    assert valor(liq, "festivo_nocturno") == Decimal(129_000)
    assert adicional(liq) == Decimal(146_500)


def test_4_domingo_a_lunes_festivo_caso_contadora():
    """Domingo 18:00 → lunes festivo 06:00 (29-jun-2026, San Pedro).

    «Los sábados o domingos que al siguiente día es festivo, cambia a festivo
    después de las 12 de la noche»: el corte en 00:00 lo produce solo.
    Dom 18-19 diurna dominical: 1 h × 1,80 = 18.000 · dom 19-24 nocturna
    dominical: 5 h × 2,15 = 107.500 · lun-festivo 00-06: 6 h × 2,15 = 129.000.
    """
    turnos = [turno("2026-06-28", "18:00", "06:00")]
    tramos = segmentar_turnos(turnos, PARAMETROS, CALENDARIO)
    tras_medianoche = [t for t in tramos if t.fecha == date(2026, 6, 29)]
    assert all(t.tipo_dia is TipoDia.FESTIVO for t in tras_medianoche)
    assert sum(t.minutos for t in tras_medianoche) == 6 * 60

    liq = liquidar_turnos(turnos, desde="2026-06-16")
    assert valor(liq, "festivo_diurno") == Decimal(18_000)
    assert valor(liq, "festivo_nocturno") == Decimal(107_500 + 129_000)
    assert adicional(liq) == Decimal(254_500)


def test_5_quincena_cruza_cambio_de_jornada_44_a_42():
    """1–15 jul 2026: la jornada máxima semanal baja de 44 a 42 h el 15-jul.

    Turnos de 15 h (06:00-21:00) el lun 13, mar 14 y mié 15 (misma semana ISO).
    Con `semanal_legal`: acumulado 30 h al llegar al 15-jul, cuyo límite vigente
    ya es 42 h → ordinarias hasta las 18:00 (12 h) y extra 18:00-21:00
    (1 h extra diurna + 2 h extra nocturna). Con el límite viejo (44 h) la extra
    habría empezado a las 20:00: la vigencia se evalúa en la fecha del tramo.
    """
    turnos = [
        turno("2026-07-13", "06:00", "21:00"),
        turno("2026-07-14", "06:00", "21:00"),
        turno("2026-07-15", "06:00", "21:00"),
    ]
    liq = liquidar_turnos(turnos, desde="2026-07-01", estrategia="semanal_legal")
    # nocturnas ordinarias: 19-21 del lun y mar = 4 h × 3.500
    assert valor(liq, "recargo_nocturno") == Decimal(14_000)
    assert valor(liq, "extra_diurna") == Decimal(12_500)  # 1 h × 1,25
    assert valor(liq, "extra_nocturna") == Decimal(35_000)  # 2 h × 1,75
    assert adicional(liq) == Decimal(61_500)

    # Con la estrategia de la contadora (110 h/quincena) 45 h no generan extras
    liq_quincenal = liquidar_turnos(turnos, desde="2026-07-01",
                                    estrategia="presupuesto_quincenal")
    assert valor(liq_quincenal, "recargo_nocturno") == Decimal(21_000)  # 6 h noct.
    assert adicional(liq_quincenal) == Decimal(21_000)


def test_6_recargo_dominical_cambia_80_a_90_el_1_jul_2026():
    """Mismo turno dominical antes y después del 1-jul-2026: 80% → 90%."""
    antes = liquidar_turnos([turno("2026-06-28", "08:00", "16:00")], desde="2026-06-16")
    despues = liquidar_turnos([turno("2026-07-05", "08:00", "16:00")], desde="2026-07-01")
    assert valor(antes, "festivo_diurno") == Decimal(144_000)  # 8 h × 1,80
    assert valor(despues, "festivo_diurno") == Decimal(152_000)  # 8 h × 1,90

    # el factor queda desglosado en componentes auditables
    concepto = next(c for c in despues.conceptos if c.codigo == "festivo_diurno")
    assert concepto.componentes == {
        "hora_base": Decimal(1),
        "recargo_dominical_festivo": Decimal("0.90"),
    }


def test_7_festivo_trasladado_por_ley_emiliani():
    """Reyes 2026 (6-ene, martes) se paga como festivo el lunes 12-ene."""
    en_festivo_trasladado = liquidar_turnos(
        [turno("2026-01-12", "08:00", "16:00")], desde="2026-01-01"
    )
    assert valor(en_festivo_trasladado, "festivo_diurno") == Decimal(144_000)

    # y el 6 de enero fue un martes ordinario: sin pago adicional
    en_fecha_original = liquidar_turnos(
        [turno("2026-01-06", "08:00", "16:00")], desde="2026-01-01"
    )
    assert adicional(en_fecha_original) == 0


def test_tarifas_coinciden_con_planilla_contadora():
    """Réplica de la planilla NOMINA MAYO THUNAPA (salario mínimo 2026)."""
    salario = Decimal(1_750_905)
    fecha = date(2026, 5, 1)
    tarifa = salario / PARAMETROS.divisor_hora_ordinaria(fecha)
    centavos = Decimal("0.0001")
    assert tarifa.quantize(centavos) == Decimal("7958.6591")
    # recargo nocturno por hora: su planilla dice 2785.5306818...
    assert (tarifa * PARAMETROS.recargo_nocturno(fecha)).quantize(centavos) == Decimal("2785.5307")
    # extra diurna 9948.32, extra nocturna 13927.65, festivo 14325.59
    assert (tarifa * Decimal("1.25")).quantize(centavos) == Decimal("9948.3239")
    assert (tarifa * Decimal("1.75")).quantize(centavos) == Decimal("13927.6534")
    assert (tarifa * Decimal("1.80")).quantize(centavos) == Decimal("14325.5864")


def test_auxilio_de_transporte_quincenal():
    liq = liquidar(
        [], SALARIO, PARAMETROS, date(2026, 5, 1), incluir_auxilio_transporte=True
    )
    # 249.095 / 2 = 124.547,50 → redondeo final a peso: 124.548
    assert valor(liq, "auxilio_transporte") == Decimal(124_548)


def test_auxilio_prorrateado_paga_en_proporcion_a_lo_laborado():
    """El empleado solo alcanzó a trabajar parte de la quincena: el auxilio se paga
    en proporción a lo laborado, `mensual × horas / horas del mes`."""
    turnos = [turno("2026-05-04", "06:00", "14:00")]  # lunes, 8 h ordinarias
    tramos = segmentar_turnos(turnos, PARAMETROS, CALENDARIO)
    clasificados = clasificar_extras(tramos, PARAMETROS, date(2026, 5, 1))
    liq = liquidar(clasificados, SALARIO, PARAMETROS, date(2026, 5, 1),
                   incluir_auxilio_transporte=True, auxilio_prorrateado=True)
    # 249.095 × 8 / 220 = 9.058 exactos
    assert valor(liq, "auxilio_transporte") == Decimal(9_058)
    concepto = next(c for c in liq.conceptos if c.codigo == "auxilio_transporte")
    assert concepto.componentes == {"horas_laboradas": Decimal(8)}


def test_auxilio_prorrateado_de_quincena_completa_es_el_quincenal():
    """Invariante: al agotar el presupuesto de la quincena, el prorrateo da el mismo
    valor que el auxilio plano, así que marcar la casilla de más no cambia nada."""
    # 14 turnos de 8 h = 112 h: las 2 h que exceden las 110 se clasifican extra,
    # así que la base no-extra queda exactamente en el presupuesto.
    turnos = [turno(f"2026-05-{d:02d}", "06:00", "14:00") for d in range(4, 16)]
    turnos += [turno("2026-05-18", "06:00", "14:00"), turno("2026-05-19", "06:00", "14:00")]
    tramos = segmentar_turnos(turnos, PARAMETROS, CALENDARIO)
    clasificados = clasificar_extras(tramos, PARAMETROS, date(2026, 5, 1))
    liq = liquidar(clasificados, SALARIO, PARAMETROS, date(2026, 5, 1),
                   incluir_auxilio_transporte=True, auxilio_prorrateado=True)
    assert valor(liq, "auxilio_transporte") == Decimal(124_548)


def test_auxilio_prorrateado_sin_horas_laboradas_es_cero():
    """Cero horas: el auxilio es 0, pero la línea se emite igual (con las horas a la
    vista) para que el cero quede explicado en el reporte."""
    liq = liquidar([], SALARIO, PARAMETROS, date(2026, 5, 1),
                   incluir_auxilio_transporte=True, auxilio_prorrateado=True)
    assert valor(liq, "auxilio_transporte") == Decimal(0)
    concepto = next(c for c in liq.conceptos if c.codigo == "auxilio_transporte")
    assert concepto.componentes == {"horas_laboradas": Decimal(0)}


def test_quincena_incompleta_paga_solo_horas_trabajadas():
    """Marcado a mano que el empleado no laboró toda la quincena (incapacidad,
    ausencia, ingreso/retiro a mitad de periodo): las ordinarias se pagan sobre
    lo trabajado, no sobre el tope legal. Sin la marca, el comportamiento no
    cambia (así lo calibran los golden tests de Puebla)."""
    turnos = [turno("2026-03-02", "06:00", "14:00")]  # 8 h diurnas ordinarias
    tramos = segmentar_turnos(turnos, PARAMETROS, CALENDARIO)
    clasificados = clasificar_extras(tramos, PARAMETROS, date(2026, 3, 1))

    completa = liquidar(
        clasificados, SALARIO, PARAMETROS, date(2026, 3, 1),
        incluir_auxilio_transporte=False,
    )
    assert valor(completa, "tiempo_ordinario") == BASE_QUINCENA

    incompleta = liquidar(
        clasificados, SALARIO, PARAMETROS, date(2026, 3, 1),
        incluir_auxilio_transporte=False, quincena_completa=False,
    )
    assert valor(incompleta, "tiempo_ordinario") == Decimal(80_000)  # 8 h × 10.000


def test_quincena_incompleta_cuenta_tambien_las_horas_festivas():
    """Con la quincena incompleta el tiempo ordinario cubre TODAS las horas
    laboradas, festivas incluidas, y el festivo se paga aparte con su factor.

    Es como lo liquida la contadora (hoja HERNAN 1-15 de agosto: 49 h trabajadas →
    49 h de TIEMPO ORDINARIO, con 14 h festivas dentro, más TIEMPO FESTIVO ×1.90),
    y es lo coherente con la quincena completa, donde el presupuesto de horas ya
    incluye las festivas: excluirlas solo al prorratear le pagaría menos al empleado
    parcial que al completo por la misma hora festiva."""
    turnos = [
        turno("2026-03-02", "06:00", "14:00"),  # lunes, 8 h diurnas ordinarias
        turno("2026-03-08", "06:00", "14:00"),  # domingo, 8 h dominicales
    ]
    tramos = segmentar_turnos(turnos, PARAMETROS, CALENDARIO)
    clasificados = clasificar_extras(tramos, PARAMETROS, date(2026, 3, 1))
    liq = liquidar(
        clasificados, SALARIO, PARAMETROS, date(2026, 3, 1),
        incluir_auxilio_transporte=False, quincena_completa=False,
    )
    assert valor(liq, "tiempo_ordinario") == Decimal(160_000)  # 16 h: lunes Y domingo
    assert valor(liq, "festivo_diurno") == Decimal(144_000)  # 8 h × 1,80
    assert liq.total_devengado == Decimal(304_000)


def test_nocturna_dentro_de_jornada_solo_paga_recargo():
    """La hora nocturna ordinaria ya está cubierta por el salario: paga solo
    el 35% (así lo liquida la contadora: TIEMPO NOCTURNO a tarifa × 0,35)."""
    liq = liquidar_turnos([turno("2026-03-09", "19:00", "23:00")], desde="2026-03-01")
    concepto = next(c for c in liq.conceptos if c.codigo == "recargo_nocturno")
    assert concepto.factor == Decimal("0.35")
    assert concepto.componentes == {"recargo_nocturno": Decimal("0.35")}
    assert concepto.valor == Decimal(14_000)  # 4 h × 3.500


# --- Jornada ordinaria: turno registrado solo para cuadrar horas ---


def test_jornada_ordinaria_dentro_del_umbral_no_paga_nada():
    """Domingo 06:00-13:00 (7 h) marcado con umbral 7 h: el empleado no trabajó,
    el turno solo cuadra las horas de la quincena → ningún pago adicional."""
    liq = liquidar_turnos(
        [turno("2026-03-08", "06:00", "13:00", jornada_ordinaria_h=7)], desde="2026-03-01"
    )
    assert valor(liq, "tiempo_ordinario") == BASE_QUINCENA
    assert adicional(liq) == 0


def test_jornada_ordinaria_solo_reconoce_el_excedente_como_extra_festiva():
    """Domingo 06:00-16:00 (10 h) con umbral 7 h: las 3 h de más sí se reconocen,
    como festivas Y extra → 3 h × (1 + 0,25 + 0,80) = 3 × 20.500 = 61.500."""
    liq = liquidar_turnos(
        [turno("2026-03-08", "06:00", "16:00", jornada_ordinaria_h=7)], desde="2026-03-01"
    )
    assert valor(liq, "festivo_diurno") == 0  # las 7 h neutras no pagan recargo
    concepto = next(c for c in liq.conceptos if c.codigo == "extra_diurna_festiva")
    assert concepto.minutos == 3 * 60
    assert concepto.factor == Decimal("2.05")
    assert concepto.valor == Decimal(61_500)
    assert adicional(liq) == Decimal(61_500)


def test_jornada_ordinaria_tampoco_paga_recargo_nocturno():
    """Domingo 18:00 → lunes 04:00 con umbral 7 h. Las primeras 7 h no pagan ni
    dominical ni nocturno; las 3 h restantes (lun 01:00-04:00, día ordinario)
    son extra nocturna: 3 h × (1 + 0,75) = 3 × 17.500 = 52.500."""
    liq = liquidar_turnos(
        [turno("2026-03-08", "18:00", "04:00", jornada_ordinaria_h=7)], desde="2026-03-01"
    )
    assert valor(liq, "recargo_nocturno") == 0
    assert valor(liq, "festivo_nocturno") == 0
    assert valor(liq, "extra_nocturna") == Decimal(52_500)
    assert adicional(liq) == Decimal(52_500)


def test_jornada_ordinaria_cuenta_como_hora_trabajada_si_la_quincena_es_incompleta():
    """Las horas neutras sí son horas ordinarias de la quincena: con quincena
    incompleta deben sumar al balde de tiempo_ordinario aunque caigan en domingo
    (no se pagan aparte, el salario es su única remuneración)."""
    turnos = [turno("2026-03-08", "06:00", "14:00", jornada_ordinaria_h=8)]  # domingo, 8 h
    tramos = segmentar_turnos(turnos, PARAMETROS, CALENDARIO)
    clasificados = clasificar_extras(tramos, PARAMETROS, date(2026, 3, 1))
    liq = liquidar(
        clasificados, SALARIO, PARAMETROS, date(2026, 3, 1),
        incluir_auxilio_transporte=False, quincena_completa=False,
    )
    assert valor(liq, "tiempo_ordinario") == Decimal(80_000)  # 8 h × 10.000
    assert liq.total_devengado == Decimal(80_000)


def test_tiempo_ordinario_de_agosto_2026_es_salario_medio():
    """Con el par vigente desde el 15-jul-2026 (105 h / divisor 210), el tiempo
    ordinario de una quincena completa da exactamente salario/2.

    Fija el valor que estaba mal en la base del usuario: con `horas_quincena` = 110
    quedado y el divisor ya en 210, pagaba 1.152.381 — 52.381 de más por empleado.
    """
    liq = liquidar([], SALARIO, PARAMETROS, date(2026, 8, 1))
    assert valor(liq, "tiempo_ordinario") == SALARIO / 2 == Decimal(1_100_000)
    # Y antes del corte, con el par viejo (110 h / divisor 220), también da salario/2.
    liq_antes = liquidar([], SALARIO, PARAMETROS, date(2026, 7, 1))
    assert valor(liq_antes, "tiempo_ordinario") == SALARIO / 2
