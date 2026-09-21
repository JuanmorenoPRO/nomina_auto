"""Caso de uso: importar los turnos de una quincena desde la plantilla Excel.

El archivo tiene el formato de la tarjeta de turnos (el cuadro detallado): una
hoja por empleado y una fila por día. El lector de Excel vive en
infraestructura y entrega aquí datos puros (`LibroTurnos`), así que este módulo
no sabe nada de openpyxl.

Reglas acordadas con la contadora:

- **La clave del empleado es la C.C.**, no el nombre de la hoja (que Excel trunca
  a 31 caracteres y ella puede renombrar).
- **Reemplazo por empleado:** la hoja de un empleado deja sus turnos del periodo
  exactamente como dice el archivo. Los empleados que no aparecen en el archivo
  no se tocan.
- **No se crean empleados:** una hoja con una C.C. desconocida se reporta.
- **Todo o nada:** primero se valida el libro completo; si hay un solo error no
  se escribe nada. Una importación a medias dejaría la quincena en un estado que
  nadie puede auditar, y esto alimenta dinero.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, time, timedelta
from decimal import Decimal
from typing import Protocol
from uuid import UUID, uuid4

from nomina.aplicacion.errores import NoEncontradoError, ReglaDeNegocioError
from nomina.dominio.entidades.empleado import Empleado
from nomina.dominio.entidades.periodo_liquidacion import EstadoPeriodo, PeriodoLiquidacion
from nomina.dominio.entidades.turno import Turno, TurnoRegistrado, validar_sin_solapamientos
from nomina.dominio.puertos.repositorios import (
    RepositorioEmpleados,
    RepositorioPeriodos,
    RepositorioTurnos,
)

# --- Lo que entrega el lector de Excel (datos puros) ---


@dataclass(frozen=True)
class FilaTurno:
    """Una fila de la tabla de una hoja. `fila` es el número de fila en Excel,
    para poder señalar el error donde la contadora lo va a ver."""

    fila: int
    dia_del_mes: int | None = None
    hora_inicio: time | None = None
    hora_fin: time | None = None
    horas_jornada_ordinaria: Decimal | None = None
    error: str = ""


@dataclass(frozen=True)
class MarcasHoja:
    """Marcas por empleado y quincena leídas del encabezado de la hoja.
    `None` = la fila no venía en el archivo, así que no se pisa lo que haya."""

    quincena_incompleta: bool | None = None
    sin_extras: bool | None = None
    auxilio_por_dias_laborados: bool | None = None
    pagar_dia_31: bool | None = None

    def como_dict(self) -> dict[str, bool]:
        return {
            nombre: valor
            for nombre, valor in (
                ("quincena_incompleta", self.quincena_incompleta),
                ("sin_extras", self.sin_extras),
                ("auxilio_por_dias_laborados", self.auxilio_por_dias_laborados),
                ("pagar_dia_31", self.pagar_dia_31),
            )
            if valor is not None
        }


@dataclass(frozen=True)
class HojaTurnos:
    nombre_hoja: str
    documento: str = ""
    nombre_empleado: str = ""
    unidad: str = ""
    filas: tuple[FilaTurno, ...] = ()
    marcas: MarcasHoja = field(default_factory=MarcasHoja)
    errores: tuple[str, ...] = ()


@dataclass(frozen=True)
class LibroTurnos:
    hojas: tuple[HojaTurnos, ...] = ()
    ignoradas: tuple[str, ...] = ()


class LectorTurnosExcel(Protocol):
    """Puerto: convierte el .xlsx en datos puros. Lanza `ValueError` si el
    archivo no es un libro de Excel legible."""

    def __call__(self, contenido: bytes) -> LibroTurnos: ...


class RepositorioMarcasQuincena(Protocol):
    """Puerto de escritura de las marcas por empleado y quincena (el de lectura
    lo declara `liquidar_quincena.RepositorioAjustesQuincena`)."""

    def marcar(
        self,
        empleado_id: UUID,
        periodo_id: UUID,
        *,
        quincena_incompleta: bool | None = None,
        sin_extras: bool | None = None,
        auxilio_por_dias_laborados: bool | None = None,
        pagar_dia_31: bool | None = None,
    ) -> None: ...


# --- Reporte ---


@dataclass(frozen=True)
class ErrorImportacion:
    hoja: str
    mensaje: str
    fila: int | None = None


@dataclass(frozen=True)
class HojaImportada:
    hoja: str
    documento: str
    empleado: str
    turnos_creados: int
    turnos_borrados: int
    minutos: int
    marcas: dict[str, bool]

    @property
    def horas(self) -> Decimal:
        return (Decimal(self.minutos) / 60).quantize(Decimal("0.01"))


@dataclass(frozen=True)
class ReporteImportacion:
    aplicado: bool
    hojas: tuple[HojaImportada, ...] = ()
    ignoradas: tuple[str, ...] = ()
    errores: tuple[ErrorImportacion, ...] = ()

    @property
    def tiene_errores(self) -> bool:
        return bool(self.errores)


def normalizar_documento(documento: str) -> str:
    """La C.C. se compara sin puntos, espacios ni guiones: en Excel la misma
    cédula aparece como 1.032.456, 1032456 o '1032456 '."""
    return "".join(c for c in documento if c.isalnum()).upper()


def _fechas_por_dia(periodo: PeriodoLiquidacion) -> dict[int, date]:
    """Día del mes → fecha del periodo. Si un número se repite (un periodo que
    cruza de mes y dura más de 16 días) el día queda fuera del mapa y la fila
    se reporta como ambigua."""
    conteo: dict[int, int] = {}
    mapa: dict[int, date] = {}
    dia = periodo.fecha_inicio
    while dia <= periodo.fecha_fin:
        conteo[dia.day] = conteo.get(dia.day, 0) + 1
        mapa[dia.day] = dia
        dia += timedelta(days=1)
    return {numero: fecha for numero, fecha in mapa.items() if conteo[numero] == 1}


@dataclass(frozen=True)
class _HojaPreparada:
    hoja: HojaTurnos
    empleado: Empleado
    nuevos: list[TurnoRegistrado]
    a_borrar: list[TurnoRegistrado]


@dataclass(frozen=True)
class ImportarTurnos:
    empleados: RepositorioEmpleados
    periodos: RepositorioPeriodos
    turnos: RepositorioTurnos
    marcas: RepositorioMarcasQuincena
    lector: LectorTurnosExcel

    def ejecutar(
        self,
        unidad_id: UUID,
        periodo_id: UUID,
        contenido: bytes,
        aplicar: bool = True,
    ) -> ReporteImportacion:
        periodo = self.periodos.obtener(periodo_id)
        if periodo is None:
            raise NoEncontradoError(f"No existe el periodo {periodo_id}")
        if periodo.estado is not EstadoPeriodo.ABIERTO:
            raise ReglaDeNegocioError(
                f"El periodo {periodo.fecha_inicio}–{periodo.fecha_fin} está "
                f"{periodo.estado.value}: reábralo para importar turnos"
            )

        try:
            libro = self.lector(contenido)
        except ValueError as e:
            raise ReglaDeNegocioError(str(e)) from e

        if not libro.hojas:
            raise ReglaDeNegocioError(
                "El archivo no tiene ninguna hoja con el formato de la plantilla de "
                "turnos (se busca una fila de encabezado con ENTRA y SALE, y la C.C. "
                "del empleado)"
            )

        por_documento = {
            normalizar_documento(e.documento): e
            for e in self.empleados.listar(unidad_id=unidad_id)
        }
        fechas = _fechas_por_dia(periodo)

        errores: list[ErrorImportacion] = []
        preparadas: list[_HojaPreparada] = []
        documentos_vistos: dict[str, str] = {}

        for hoja in libro.hojas:
            for mensaje in hoja.errores:
                errores.append(ErrorImportacion(hoja=hoja.nombre_hoja, mensaje=mensaje))

            documento = normalizar_documento(hoja.documento)
            if not documento:
                continue  # el lector ya reportó que a la hoja le falta la C.C.
            empleado = por_documento.get(documento)
            if empleado is None:
                errores.append(
                    ErrorImportacion(
                        hoja=hoja.nombre_hoja,
                        mensaje=(
                            f"No hay ningún empleado con C.C. «{hoja.documento}» en esta "
                            "unidad. La importación no crea empleados: créelo primero en "
                            "«Unidades y empleados»."
                        ),
                    )
                )
                continue
            if not empleado.activo:
                errores.append(
                    ErrorImportacion(
                        hoja=hoja.nombre_hoja,
                        mensaje=f"El empleado {empleado.nombre} está inactivo",
                    )
                )
                continue
            if documento in documentos_vistos:
                errores.append(
                    ErrorImportacion(
                        hoja=hoja.nombre_hoja,
                        mensaje=(
                            f"La C.C. «{hoja.documento}» ya venía en la hoja "
                            f"«{documentos_vistos[documento]}»: dos hojas del mismo "
                            "empleado se contradicen entre sí."
                        ),
                    )
                )
                continue
            documentos_vistos[documento] = hoja.nombre_hoja

            preparada = self._preparar(hoja, empleado, periodo, fechas, errores)
            if preparada is not None:
                preparadas.append(preparada)

        if errores:
            return ReporteImportacion(
                aplicado=False,
                hojas=tuple(self._resumir(p) for p in preparadas),
                ignoradas=libro.ignoradas,
                errores=tuple(errores),
            )

        if aplicar:
            for p in preparadas:
                for viejo in p.a_borrar:
                    self.turnos.eliminar(viejo.id)
                for nuevo in p.nuevos:
                    self.turnos.guardar(nuevo)
                marcas = p.hoja.marcas
                if marcas.como_dict():
                    self.marcas.marcar(
                        p.empleado.id,
                        periodo.id,
                        quincena_incompleta=marcas.quincena_incompleta,
                        sin_extras=marcas.sin_extras,
                        auxilio_por_dias_laborados=marcas.auxilio_por_dias_laborados,
                        pagar_dia_31=marcas.pagar_dia_31,
                    )

        return ReporteImportacion(
            aplicado=aplicar,
            hojas=tuple(self._resumir(p) for p in preparadas),
            ignoradas=libro.ignoradas,
        )

    def _preparar(
        self,
        hoja: HojaTurnos,
        empleado: Empleado,
        periodo: PeriodoLiquidacion,
        fechas: dict[int, date],
        errores: list[ErrorImportacion],
    ) -> _HojaPreparada | None:
        nuevos: list[TurnoRegistrado] = []
        hubo_error = False

        for fila in hoja.filas:
            if fila.error:
                errores.append(
                    ErrorImportacion(hoja=hoja.nombre_hoja, fila=fila.fila, mensaje=fila.error)
                )
                hubo_error = True
                continue
            if fila.hora_inicio is None and fila.hora_fin is None:
                continue  # descanso
            if fila.hora_inicio is None or fila.hora_fin is None:
                errores.append(
                    ErrorImportacion(
                        hoja=hoja.nombre_hoja,
                        fila=fila.fila,
                        mensaje="Falta la hora de entrada o la de salida",
                    )
                )
                hubo_error = True
                continue
            if fila.dia_del_mes is None:
                errores.append(
                    ErrorImportacion(
                        hoja=hoja.nombre_hoja,
                        fila=fila.fila,
                        mensaje="La fila tiene horario pero no dice a qué día corresponde",
                    )
                )
                hubo_error = True
                continue
            fecha = fechas.get(fila.dia_del_mes)
            if fecha is None:
                errores.append(
                    ErrorImportacion(
                        hoja=hoja.nombre_hoja,
                        fila=fila.fila,
                        mensaje=(
                            f"El día {fila.dia_del_mes} no está en la quincena "
                            f"{periodo.fecha_inicio:%d/%m/%Y}–{periodo.fecha_fin:%d/%m/%Y}"
                        ),
                    )
                )
                hubo_error = True
                continue

            minutos_jornada: int | None = None
            if fila.horas_jornada_ordinaria is not None:
                minutos_exactos = fila.horas_jornada_ordinaria * 60
                if minutos_exactos != minutos_exactos.to_integral_value():
                    errores.append(
                        ErrorImportacion(
                            hoja=hoja.nombre_hoja,
                            fila=fila.fila,
                            mensaje=(
                                f"La jornada ordinaria ({fila.horas_jornada_ordinaria} h) no "
                                "da un número entero de minutos"
                            ),
                        )
                    )
                    hubo_error = True
                    continue
                minutos_jornada = int(minutos_exactos)

            try:
                turno = Turno(
                    fecha=fecha,
                    hora_inicio=fila.hora_inicio,
                    hora_fin=fila.hora_fin,
                    minutos_jornada_ordinaria=minutos_jornada,
                )
            except ValueError as e:
                errores.append(
                    ErrorImportacion(hoja=hoja.nombre_hoja, fila=fila.fila, mensaje=str(e))
                )
                hubo_error = True
                continue
            nuevos.append(
                TurnoRegistrado(id=uuid4(), empleado_id=empleado.id, turno=turno)
            )

        # Los vecinos de un día antes y uno después capturan los cruces de
        # medianoche contra la quincena anterior y la siguiente.
        vecinos = self.turnos.de_empleado_entre(
            empleado.id,
            periodo.fecha_inicio - timedelta(days=1),
            periodo.fecha_fin + timedelta(days=1),
        )
        a_borrar = [v for v in vecinos if periodo.contiene(v.turno.fecha)]
        conservados = [v for v in vecinos if not periodo.contiene(v.turno.fecha)]

        try:
            validar_sin_solapamientos([c.turno for c in conservados] + [n.turno for n in nuevos])
        except ValueError as e:
            errores.append(ErrorImportacion(hoja=hoja.nombre_hoja, mensaje=str(e)))
            hubo_error = True

        if hubo_error:
            return None
        return _HojaPreparada(hoja=hoja, empleado=empleado, nuevos=nuevos, a_borrar=a_borrar)

    def _resumir(self, p: _HojaPreparada) -> HojaImportada:
        return HojaImportada(
            hoja=p.hoja.nombre_hoja,
            documento=p.empleado.documento,
            empleado=p.empleado.nombre,
            turnos_creados=len(p.nuevos),
            turnos_borrados=len(p.a_borrar),
            minutos=sum(n.turno.minutos for n in p.nuevos),
            marcas=p.hoja.marcas.como_dict(),
        )
