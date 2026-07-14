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

Cada componente se resuelve con la vigencia de la FECHA DEL TRAMO. Redondeo:
una sola vez, al final, por concepto, a pesos enteros con ROUND_HALF_UP.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import ROUND_HALF_UP, Decimal

from nomina.dominio.entidades.concepto_liquidado import ConceptoLiquidado, Liquidacion
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
}

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
    por el salario base (ordinaria diurna en día ordinario)."""
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


def _redondear_pesos(valor: Decimal) -> Decimal:
    return valor.quantize(_UN_PESO, rounding=ROUND_HALF_UP)


def liquidar(
    tramos_clasificados: list[Tramo],
    salario_mensual: Decimal,
    parametros: ProveedorParametros,
    fecha_periodo: date,
    incluir_auxilio_transporte: bool = True,
) -> Liquidacion:
    """Liquida la quincena de un empleado a partir de sus tramos ya clasificados.

    `fecha_periodo` (inicio del periodo) fija la vigencia del divisor, las horas
    de la quincena y el auxilio de transporte; los recargos de cada tramo usan
    la vigencia de la fecha del tramo.
    """
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

    minutos_quincena = int(parametros.horas_quincena(fecha_periodo) * MINUTOS_POR_HORA)
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
        valor = Decimal(minutos) / MINUTOS_POR_HORA * tarifa_hora * factor
        conceptos.append(
            ConceptoLiquidado(
                codigo=codigo,
                nombre=NOMBRES_CONCEPTOS[codigo],
                minutos=minutos,
                tarifa_hora=tarifa_hora,
                factor=factor,
                componentes=componentes,
                valor=_redondear_pesos(valor),
            )
        )

    if incluir_auxilio_transporte:
        auxilio = parametros.auxilio_transporte_mensual(fecha_periodo) / 2
        conceptos.append(
            ConceptoLiquidado(
                codigo="auxilio_transporte",
                nombre=NOMBRES_CONCEPTOS["auxilio_transporte"],
                minutos=0,
                valor=_redondear_pesos(auxilio),
            )
        )

    return Liquidacion(
        salario_mensual=salario_mensual,
        tarifa_hora=tarifa_hora,
        conceptos=tuple(conceptos),
    )
