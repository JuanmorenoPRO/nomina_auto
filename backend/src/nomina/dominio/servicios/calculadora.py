"""Cálculo de conceptos liquidados a partir de tramos clasificados.

Modelo de pago (el de la planilla real de la contadora):

- El salario base quincenal (salario/2 = `horas_quincena` × tarifa) cubre las
  horas ordinarias trabajadas, caigan en la franja y el día que caigan.
- Cada tramo genera un pago ADICIONAL cuyo factor es la suma de componentes:
    * `hora_base` (1.0): la hora no está cubierta por el salario — aplica a
      toda hora extra y a toda hora en dominical/festivo (el descanso ya
      estaba remunerado; trabajarlo se paga de nuevo, más el recargo).
    * `recargo_dominical_festivo`: horas en domingo o festivo.
    * `recargo_nocturno`: horas nocturnas NO extra.
    * `extra_diurna` / `extra_nocturna`: horas extra según su franja.
- Una hora ordinaria diurna en día ordinario no genera pago adicional.
- Tampoco lo genera una hora dentro de la «jornada ordinaria» de un turno
  marcado como tal: el empleado no trabajó y el turno solo cuadra las horas de
  la quincena, así que no paga recargo dominical/festivo ni nocturno.

Cada componente se resuelve con la vigencia de la FECHA DEL TRAMO. Redondeo:
una sola vez, al final, por concepto, a pesos enteros con ROUND_HALF_UP.
"""

from __future__ import annotations

from dataclasses import dataclass
import calendar
from datetime import date
from decimal import ROUND_HALF_UP, Decimal

from nomina.dominio.entidades.concepto_liquidado import (
    DEDUCCION,
    ConceptoLiquidado,
    ConceptoManual,
    Liquidacion,
)
from nomina.dominio.puertos.parametros import ProveedorParametros
from nomina.dominio.valores.tiempo import MINUTOS_POR_HORA
from nomina.dominio.valores.tramo import Franja, TipoDia, Tramo

# Etiquetas de reporte: los nombres que usa la contadora en su planilla.
NOMBRES_CONCEPTOS = {
    "tiempo_ordinario": "TIEMPO ORDINARIO",
    "recargo_nocturno": "TIEMPO NOCTURNO (RECARGO)",
    "festivo_diurno": "TIEMPO FESTIVO",
    "festivo_nocturno": "TIEMPO NOCTURNO DOMINICAL/FESTIVO",
    "extra_diurna": "EXTRA DIURNA",
    "extra_nocturna": "TIEMPO EXTRA NOCTURNO",
    "extra_diurna_festiva": "TIEMPO FESTIVO EXTRA",
    "extra_nocturna_festiva": "TIEMPO EXTRA NOCTURNO DOMINICAL/FESTIVO",
    "auxilio_transporte": "AUXILIO DE TRANSPORTE",
    "dia_31": "DIA 31",
}

# Conceptos que NO forman parte del IBC de aportes de seguridad social.
NO_SALARIALES = frozenset({"auxilio_transporte"})

_UN_PESO = Decimal("1")


@dataclass(frozen=True)
class _Clasificacion:
    codigo: str
    componentes: dict[str, Decimal]

    @property
    def factor(self) -> Decimal:
        return sum(self.componentes.values(), Decimal(0))


def _clasificar(tramo: Tramo, parametros: ProveedorParametros) -> _Clasificacion | None:
    """Concepto y componentes del factor adicional de un tramo. None = cubierto
    por el salario base (ordinaria diurna en día ordinario, o jornada ordinaria
    de un turno marcado)."""
    if tramo.jornada_ordinaria and not tramo.es_extra:
        return None  # jornada ordinaria del turno: ya cubierta por el salario

    fecha = tramo.fecha
    en_descanso = tramo.tipo_dia is not TipoDia.ORDINARIO
    nocturna = tramo.franja is Franja.NOCTURNA
    componentes: dict[str, Decimal] = {}

    if tramo.es_extra:
        componentes["hora_base"] = _UN_PESO
        if nocturna:
            componentes["extra_nocturna"] = parametros.extra_nocturna(fecha)
        else:
            componentes["extra_diurna"] = parametros.extra_diurna(fecha)
        if en_descanso:
            componentes["recargo_dominical_festivo"] = parametros.recargo_dominical_festivo(fecha)
            codigo = "extra_nocturna_festiva" if nocturna else "extra_diurna_festiva"
        else:
            codigo = "extra_nocturna" if nocturna else "extra_diurna"
        return _Clasificacion(codigo, componentes)

    if en_descanso:
        componentes["hora_base"] = _UN_PESO
        componentes["recargo_dominical_festivo"] = parametros.recargo_dominical_festivo(fecha)
        if nocturna:
            componentes["recargo_nocturno"] = parametros.recargo_nocturno(fecha)
        return _Clasificacion("festivo_nocturno" if nocturna else "festivo_diurno", componentes)

    if nocturna:
        return _Clasificacion(
            "recargo_nocturno", {"recargo_nocturno": parametros.recargo_nocturno(fecha)}
        )

    return None  # ordinaria diurna en día ordinario: ya cubierta por el salario


def _dia_31_del_mes(fecha_periodo: date) -> date | None:
    """El 31 del mes del periodo, o `None` si el mes no lo tiene."""
    if calendar.monthrange(fecha_periodo.year, fecha_periodo.month)[1] < 31:
        return None
    return date(fecha_periodo.year, fecha_periodo.month, 31)


def _redondear_pesos(valor: Decimal) -> Decimal:
    return valor.quantize(_UN_PESO, rounding=ROUND_HALF_UP)


def liquidar(
    tramos_clasificados: list[Tramo],
    salario_mensual: Decimal,
    parametros: ProveedorParametros,
    fecha_periodo: date,
    incluir_auxilio_transporte: bool = True,
    auxilio_prorrateado: bool = False,
    factores_override: dict[str, Decimal] | None = None,
    conceptos_manuales: tuple[ConceptoManual, ...] = (),
    descontar_seguridad_social: bool = False,
    quincena_completa: bool = True,
    pagar_dia_31: bool = False,
) -> Liquidacion:
    """Liquida la quincena de un empleado a partir de sus tramos ya clasificados.

    `fecha_periodo` (inicio del periodo) fija la vigencia del divisor, las horas
    de la quincena y el auxilio de transporte; los recargos de cada tramo usan
    la vigencia de la fecha del tramo.

    `factores_override` reemplaza el factor aditivo de un concepto por un factor
    fijo de la unidad (planillas con tabla de factores legada). `conceptos_manuales`
    agrega devengados/deducciones cargados a mano. Si `descontar_seguridad_social`,
    se generan las deducciones de salud y pensión sobre el IBC (devengados
    salariales, sin auxilio de transporte).

    `auxilio_prorrateado` (default `False`): con `False` el auxilio de transporte es
    el quincenal plano (mensual / 2), se haya trabajado la quincena entera o un día.
    Con `True` se paga en proporción a lo laborado: `mensual × horas / divisor`, donde
    el divisor son las horas del mes, igual que el auxilio son los pesos del mes.
    Es la cuenta de la contadora (`mensual/30 × días`, con `días = horas / jornada`)
    reducida a horas, y con la quincena completa da el quincenal plano.

    `quincena_completa` (default `True`): el salario cubre el tope legal completo
    de horas ordinarias sin importar cuánto sumen los tramos (así lo hace la
    contadora: el salario es fijo y las estrategias de extras no necesariamente
    agotan el presupuesto quincenal). Si es `False` — marcado a mano cuando el
    empleado no laboró toda la quincena (incapacidad, ausencia, ingreso/retiro a
    mitad de periodo) — las horas ordinarias se pagan sobre lo efectivamente
    trabajado, topado al legal.

    `pagar_dia_31` (default `False`): la quincena 16–fin de mes se paga SIEMPRE como
    15 días (`horas_quincena` = divisor/30 × 15), tenga el mes 30 o 31. Cuando tiene 31,
    ese día es un 16.º día que el salario no cubre; marcado, sus horas no-extra se
    reconocen aparte a hora base (concepto `dia_31`). Los recargos y las extras del 31
    ya se pagan en sus propias líneas: aquí solo se agrega la hora base que falta.

    Las marcas comparten la base de «lo laborado»: todo lo trabajado que no sea extra,
    topado al presupuesto legal. Ver el comentario en el cuerpo.
    """
    override = factores_override or {}
    _dia_31 = _dia_31_del_mes(fecha_periodo)
    tarifa_hora = salario_mensual / parametros.divisor_hora_ordinaria(fecha_periodo)

    # Agrupar minutos por (concepto, factor): si una vigencia cambia dentro del
    # periodo, el mismo concepto aparece en líneas separadas por factor.
    grupos: dict[tuple[str, Decimal], tuple[int, dict[str, Decimal]]] = {}
    for tramo in tramos_clasificados:
        clasificacion = _clasificar(tramo, parametros)
        if clasificacion is None:
            continue
        clave = (clasificacion.codigo, clasificacion.factor)
        minutos, componentes = grupos.get(clave, (0, clasificacion.componentes))
        grupos[clave] = (minutos + tramo.minutos, componentes)

    conceptos: list[ConceptoLiquidado] = []

    minutos_quincena_legal = int(parametros.horas_quincena(fecha_periodo) * MINUTOS_POR_HORA)

    # Base de «lo laborado», compartida por el tiempo ordinario prorrateado y por el
    # auxilio: TODO lo trabajado que no sea extra, topado al presupuesto legal.
    #
    # Las horas festivas y nocturnas entran aquí igual que las ordinarias, porque en
    # la quincena completa también están dentro del presupuesto (la planilla de la
    # contadora liquida 105 h de TIEMPO ORDINARIO con las horas festivas incluidas, y
    # encima paga TIEMPO FESTIVO ×1.90). Excluirlas solo al prorratear le pagaría menos
    # al empleado parcial que al completo por la misma hora festiva.
    #
    # Las extras NO entran: se pagan por encima del presupuesto y su factor ya trae la
    # `hora_base`, así que contarlas aquí les pagaría la base dos veces.
    minutos_no_extra = sum(t.minutos for t in tramos_clasificados if not t.es_extra)

    # Día 31: horas que el presupuesto de 15 días no cubre. Se cuenta desde el 31
    # en adelante, no solo el día 31, para que el turno nocturno que arranca ese día
    # y cruza al 1.º del mes siguiente entre completo: ese turno se liquida en esta
    # quincena y tampoco lo cubre el presupuesto.
    #
    # Los turnos de relleno (jornada ordinaria) SÍ cuentan: lo que su marca dice es
    # que esas horas «las cubre el salario» y por eso no pagan recargo — pero el 31
    # el salario no las cubre, y sus minutos sí consumen presupuesto en el
    # clasificador. Excluirlas dejaría sin pagar el 31 a quien registra la quincena
    # entera como jornada ordinaria, que es el uso normal del cuadro de turnos.
    minutos_dia_31 = (
        sum(t.minutos for t in tramos_clasificados if not t.es_extra and t.fecha >= _dia_31)
        if pagar_dia_31 and _dia_31 is not None
        else 0
    )

    # El auxilio prorratea sobre TODO lo laborado: el 31 es un día trabajado como
    # cualquier otro. El tiempo ordinario, en cambio, descuenta las horas del 31,
    # que se pagan en su propia línea: contarlas aquí las pagaría dos veces.
    minutos_base_auxilio = min(minutos_no_extra, minutos_quincena_legal)
    minutos_base_ordinario = min(minutos_no_extra - minutos_dia_31, minutos_quincena_legal)

    # Alarma: horas trabajadas no-extra que ni el presupuesto ni el día 31 cubren.
    # El tiempo ordinario es un presupuesto fijo (`horas_quincena`), así que lo que
    # sobrepasa esa base cobra su recargo pero no su hora base — y una ordinaria
    # diurna por encima del tope no cobra nada. No cambia ningún valor liquidado:
    # solo avisa que la estrategia de extras dejó demasiadas horas como ordinarias.
    minutos_sin_hora_base = max(
        0, minutos_no_extra - minutos_dia_31 - minutos_quincena_legal
    )

    minutos_quincena = minutos_quincena_legal if quincena_completa else minutos_base_ordinario
    conceptos.append(
        ConceptoLiquidado(
            codigo="tiempo_ordinario",
            nombre=NOMBRES_CONCEPTOS["tiempo_ordinario"],
            minutos=minutos_quincena,
            tarifa_hora=tarifa_hora,
            factor=_UN_PESO,
            componentes={"hora_base": _UN_PESO},
            valor=_redondear_pesos(Decimal(minutos_quincena) / MINUTOS_POR_HORA * tarifa_hora),
        )
    )

    orden = list(NOMBRES_CONCEPTOS)
    for (codigo, factor), (minutos, componentes) in sorted(
        grupos.items(), key=lambda kv: (orden.index(kv[0][0]), kv[0][1])
    ):
        if codigo in override:
            factor_efectivo = override[codigo]
            componentes = {"factor_unidad": factor_efectivo}
        else:
            factor_efectivo = factor
        valor = Decimal(minutos) / MINUTOS_POR_HORA * tarifa_hora * factor_efectivo
        conceptos.append(
            ConceptoLiquidado(
                codigo=codigo,
                nombre=NOMBRES_CONCEPTOS[codigo],
                minutos=minutos,
                tarifa_hora=tarifa_hora,
                factor=factor_efectivo,
                componentes=componentes,
                valor=_redondear_pesos(valor),
            )
        )

    if minutos_dia_31:
        conceptos.append(
            ConceptoLiquidado(
                codigo="dia_31",
                nombre=NOMBRES_CONCEPTOS["dia_31"],
                minutos=minutos_dia_31,
                tarifa_hora=tarifa_hora,
                factor=_UN_PESO,
                componentes={"hora_base": _UN_PESO},
                valor=_redondear_pesos(Decimal(minutos_dia_31) / MINUTOS_POR_HORA * tarifa_hora),
            )
        )

    # IBC de aportes: devengados salariales por horas (todo menos auxilio y no salariales).
    ibc = sum(
        (c.valor for c in conceptos if c.codigo not in NO_SALARIALES),
        Decimal(0),
    )

    if incluir_auxilio_transporte:
        mensual = parametros.auxilio_transporte_mensual(fecha_periodo)
        if not auxilio_prorrateado:
            auxilio = mensual / 2
            componentes_auxilio: dict[str, Decimal] = {}
        else:
            # Proporción de lo laborado: pesos del mes × horas / horas del mes.
            # Se prorratea aunque la quincena se liquide completa — son dos marcas
            # independientes. `componentes` deja las horas a la vista en el reporte,
            # que si no sería un valor sin explicación.
            horas_base = Decimal(minutos_base_auxilio) / MINUTOS_POR_HORA
            auxilio = mensual * horas_base / parametros.divisor_hora_ordinaria(fecha_periodo)
            componentes_auxilio = {"horas_laboradas": horas_base}
        conceptos.append(
            ConceptoLiquidado(
                codigo="auxilio_transporte",
                nombre=NOMBRES_CONCEPTOS["auxilio_transporte"],
                minutos=0,
                componentes=componentes_auxilio,
                valor=_redondear_pesos(auxilio),
            )
        )

    deducciones: list[ConceptoLiquidado] = []
    for manual in conceptos_manuales:
        valor = _redondear_pesos(manual.valor)
        if manual.tipo == DEDUCCION:
            deducciones.append(
                ConceptoLiquidado(codigo="otra_deduccion", nombre=manual.nombre, minutos=0, valor=valor)
            )
        else:
            conceptos.append(
                ConceptoLiquidado(codigo="otro_devengado", nombre=manual.nombre, minutos=0, valor=valor)
            )
            if manual.salarial:
                ibc += valor

    if descontar_seguridad_social:
        tasa_salud = parametros.aporte_salud_empleado(fecha_periodo)
        tasa_pension = parametros.aporte_pension_empleado(fecha_periodo)
        deducciones.insert(
            0,
            ConceptoLiquidado(
                codigo="aporte_pension", nombre="PENSIÓN", minutos=0,
                factor=tasa_pension, valor=_redondear_pesos(ibc * tasa_pension),
            ),
        )
        deducciones.insert(
            0,
            ConceptoLiquidado(
                codigo="aporte_salud", nombre="SALUD", minutos=0,
                factor=tasa_salud, valor=_redondear_pesos(ibc * tasa_salud),
            ),
        )

    return Liquidacion(
        salario_mensual=salario_mensual,
        tarifa_hora=tarifa_hora,
        conceptos=tuple(conceptos),
        deducciones=tuple(deducciones),
        minutos_sin_hora_base=minutos_sin_hora_base,
    )
