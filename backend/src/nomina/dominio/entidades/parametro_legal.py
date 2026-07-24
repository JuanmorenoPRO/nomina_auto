from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, time
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
    "estrategia_clasificacion_extras",
    "horas_jornada_diaria",
    "aporte_salud_empleado",
    "aporte_pension_empleado",
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

    def estrategia_clasificacion_extras(self, fecha: date) -> str:
        return self.valor("estrategia_clasificacion_extras", fecha)

    def horas_jornada_diaria(self, fecha: date) -> Decimal:
        return self.decimal("horas_jornada_diaria", fecha)

    def aporte_salud_empleado(self, fecha: date) -> Decimal:
        return self.decimal("aporte_salud_empleado", fecha)

    def aporte_pension_empleado(self, fecha: date) -> Decimal:
        return self.decimal("aporte_pension_empleado", fecha)
