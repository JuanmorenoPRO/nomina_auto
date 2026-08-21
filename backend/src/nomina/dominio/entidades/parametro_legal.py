from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, time, timedelta
from decimal import Decimal

from nomina.dominio.valores.vigencia import Vigencia


class ParametroNoVigenteError(LookupError):
    """No existe un valor vigente del parámetro para la fecha consultada."""


# Códigos administrables desde configuración (RF5). Rechazar códigos desconocidos
# evita typos que dejarían al motor sin parámetro vigente.
CODIGOS_PARAMETROS = frozenset({
    "jornada_nocturna_inicio",
    "jornada_nocturna_fin",
    "recargo_nocturno",
    "extra_diurna",
    "extra_nocturna",
    "recargo_dominical_festivo",
    "jornada_maxima_semanal",
    "horas_quincena",
    "divisor_hora_ordinaria",
    "tope_horas_extra_dia",
    "auxilio_transporte_mensual",
    "dias_mes_auxilio_transporte",
    "estrategia_clasificacion_extras",
    "horas_jornada_diaria",
    "aporte_salud_empleado",
    "aporte_pension_empleado",
    # Tasas de apropiaciones de seguridad social (segunda quincena)
    "aprop_sena",
    "aprop_icbf",
    "aprop_caja_compensacion",
    "aprop_salud_total",
    "aprop_pension_total",
    "aprop_arl",
    "aprop_vacaciones",
    "aprop_prima",
    "aprop_cesantias",
    "aprop_intereses_cesantias",
})


@dataclass(frozen=True)
class ParametroLegal:
    """Un valor legal con su vigencia. El valor se guarda como texto y se
    interpreta según el parámetro (Decimal, hora, o identificador)."""

    codigo: str
    valor: str
    vigencia: Vigencia
    norma: str = ""


@dataclass(frozen=True)
class ConjuntoParametros:
    """Resuelve el valor vigente de cada parámetro EN LA FECHA DEL TRAMO.

    Implementa el puerto ProveedorParametros. Valida al construirse que las
    vigencias de un mismo código no se solapen.
    """

    parametros: tuple[ParametroLegal, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        por_codigo: dict[str, list[ParametroLegal]] = {}
        for p in self.parametros:
            por_codigo.setdefault(p.codigo, []).append(p)
        for codigo, grupo in por_codigo.items():
            for i, a in enumerate(grupo):
                for b in grupo[i + 1 :]:
                    if a.vigencia.se_solapa_con(b.vigencia):
                        raise ValueError(
                            f"Vigencias solapadas para '{codigo}': {a.vigencia} y {b.vigencia}"
                        )

    def valor(self, codigo: str, fecha: date) -> str:
        for p in self.parametros:
            if p.codigo == codigo and p.vigencia.contiene(fecha):
                return p.valor
        raise ParametroNoVigenteError(f"Sin valor vigente de '{codigo}' para {fecha}")

    def decimal(self, codigo: str, fecha: date) -> Decimal:
        return Decimal(self.valor(codigo, fecha))

    # --- Accesores tipados usados por el motor ---

    def jornada_nocturna(self, fecha: date) -> tuple[time, time]:
        """(inicio, fin) de la franja nocturna vigente ese día, ej. (19:00, 06:00)."""
        return (
            time.fromisoformat(self.valor("jornada_nocturna_inicio", fecha)),
            time.fromisoformat(self.valor("jornada_nocturna_fin", fecha)),
        )

    def recargo_nocturno(self, fecha: date) -> Decimal:
        return self.decimal("recargo_nocturno", fecha)

    def extra_diurna(self, fecha: date) -> Decimal:
        return self.decimal("extra_diurna", fecha)

    def extra_nocturna(self, fecha: date) -> Decimal:
        return self.decimal("extra_nocturna", fecha)

    def recargo_dominical_festivo(self, fecha: date) -> Decimal:
        return self.decimal("recargo_dominical_festivo", fecha)

    def jornada_maxima_semanal(self, fecha: date) -> Decimal:
        return self.decimal("jornada_maxima_semanal", fecha)

    def horas_quincena(self, fecha: date) -> Decimal:
        return self.decimal("horas_quincena", fecha)

    def divisor_hora_ordinaria(self, fecha: date) -> Decimal:
        return self.decimal("divisor_hora_ordinaria", fecha)

    def auxilio_transporte_mensual(self, fecha: date) -> Decimal:
        return self.decimal("auxilio_transporte_mensual", fecha)

    def dias_mes_auxilio_transporte(self, fecha: date) -> Decimal:
        return self.decimal("dias_mes_auxilio_transporte", fecha)

    def estrategia_clasificacion_extras(self, fecha: date) -> str:
        return self.valor("estrategia_clasificacion_extras", fecha)

    def horas_jornada_diaria(self, fecha: date) -> Decimal:
        return self.decimal("horas_jornada_diaria", fecha)

    def aporte_salud_empleado(self, fecha: date) -> Decimal:
        return self.decimal("aporte_salud_empleado", fecha)

    def aporte_pension_empleado(self, fecha: date) -> Decimal:
        return self.decimal("aporte_pension_empleado", fecha)

    def tasas_apropiaciones(self, fecha: date) -> dict[str, Decimal]:
        """Tasas vigentes para la hoja de apropiaciones de seguridad social."""
        codigos = [
            "aprop_sena", "aprop_icbf", "aprop_caja_compensacion",
            "aprop_salud_total", "aprop_pension_total", "aprop_arl",
            "aprop_vacaciones", "aprop_prima", "aprop_cesantias",
            "aprop_intereses_cesantias",
        ]
        return {c: self.decimal(c, fecha) for c in codigos}


@dataclass(frozen=True)
class IncoherenciaParametros:
    """Un tramo de fechas en que dos parámetros acoplados no cuadran entre sí."""

    desde: date
    hasta: date | None
    detalle: str


def incoherencias_horas_quincena(conjunto: ConjuntoParametros) -> list[IncoherenciaParametros]:
    """Tramos donde se rompe `divisor_hora_ordinaria == 2 × horas_quincena`.

    Los dos parámetros son un par acoplado: el motor paga el salario quincenal como
    `horas_quincena × (salario / divisor)`, que solo da `salario / 2` si el divisor es
    el doble de las horas. Cambiar uno sin el otro (ej. bajar el divisor a 210 por la
    jornada de 42 h y dejar las horas en 110) sobrepaga o subpaga el tiempo ordinario
    sin que nada lo avise.

    Se reporta, NO se impone: elevarlo a error en `ConjuntoParametros.__post_init__`
    dejaría la aplicación caída en cualquier base que ya arrastre el descuadre, que es
    justo cuando hace falta poder entrar a corregirlo. Lista vacía = todo cuadrado.
    """
    cortes = sorted(
        {
            p.vigencia.desde
            for p in conjunto.parametros
            if p.codigo in ("horas_quincena", "divisor_hora_ordinaria")
        }
    )
    hallazgos: list[IncoherenciaParametros] = []
    for i, desde in enumerate(cortes):
        # El tramo va hasta el día anterior al siguiente corte (o abierto si es el último).
        siguiente = cortes[i + 1] if i + 1 < len(cortes) else None
        hasta = siguiente - timedelta(days=1) if siguiente else None
        try:
            horas = conjunto.horas_quincena(desde)
            divisor = conjunto.divisor_hora_ordinaria(desde)
        except ParametroNoVigenteError:
            continue  # sin valor vigente ahí: no hay nada que comparar
        if divisor != horas * 2:
            hallazgos.append(
                IncoherenciaParametros(
                    desde=desde,
                    hasta=hasta,
                    detalle=(
                        f"horas_quincena = {horas} y divisor_hora_ordinaria = {divisor} "
                        f"no cuadran: el divisor debe ser el doble de las horas. El par "
                        f"correcto es {horas}/{horas * 2} o {divisor / 2}/{divisor}. "
                        f"Mientras tanto el tiempo ordinario no paga salario/2."
                    ),
                )
            )
    return hallazgos
