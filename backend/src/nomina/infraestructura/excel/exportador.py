"""Exportador de liquidaciones a Excel con el formato de la planilla de la
contadora: una hoja por empleado con el desglose por concepto, más un resumen."""

from __future__ import annotations

import re
from io import BytesIO

from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, Side
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.worksheet import Worksheet

from nomina.aplicacion.casos_uso.liquidar_quincena import (
    LiquidacionEmpleado,
    LiquidacionQuincena,
)

_NEGRITA = Font(bold=True)
_TITULO = Font(bold=True, size=13)
_PESOS = "#,##0"
_BORDE_FINO = Border(bottom=Side(style="thin"))


def _titulo_hoja(nombre: str) -> str:
    """Excel limita títulos a 31 caracteres y prohíbe []:*?/\\"""
    return re.sub(r"[\[\]:*?/\\]", "", nombre).strip()[:31] or "EMPLEADO"


def _encabezado(hoja: Worksheet, liq: LiquidacionQuincena) -> None:
    hoja["A1"] = liq.unidad.nombre
    hoja["A1"].font = _TITULO
    hoja["A2"] = f"NIT: {liq.unidad.nit}" if liq.unidad.nit else ""
    hoja["A3"] = (
        f"PERIODO DE PAGO: {liq.periodo.fecha_inicio:%d/%m/%Y} AL "
        f"{liq.periodo.fecha_fin:%d/%m/%Y}  (versión {liq.version})"
    )
    hoja["A3"].font = _NEGRITA


def _hoja_empleado(hoja: Worksheet, liq: LiquidacionQuincena, le: LiquidacionEmpleado) -> None:
    _encabezado(hoja, liq)
    hoja["A5"] = "EMPLEADO:"
    hoja["B5"] = le.empleado.nombre
    hoja["B5"].font = _NEGRITA
    hoja["D5"] = "CÉDULA:"
    hoja["E5"] = le.empleado.documento
    hoja["A6"] = "SALARIO BÁSICO MENSUAL:"
    hoja["C6"] = int(le.liquidacion.salario_mensual)
    hoja["C6"].number_format = _PESOS
    hoja["D6"] = "TARIFA HORA:"
    hoja["E6"] = float(round(le.liquidacion.tarifa_hora, 2))
    hoja["E6"].number_format = "#,##0.00"

    encabezados = ["CONCEPTO", "HORAS", "FACTOR", "VALOR"]
    fila = 8
    for col, texto in enumerate(encabezados, start=1):
        celda = hoja.cell(row=fila, column=col, value=texto)
        celda.font = _NEGRITA
        celda.border = _BORDE_FINO

    for concepto in le.liquidacion.conceptos:
        fila += 1
        hoja.cell(row=fila, column=1, value=concepto.nombre)
        if concepto.minutos:
            celda_horas = hoja.cell(row=fila, column=2, value=float(round(concepto.horas, 2)))
            celda_horas.number_format = "0.00"
        if concepto.factor is not None:
            hoja.cell(row=fila, column=3, value=float(concepto.factor)).number_format = "0.00"
        hoja.cell(row=fila, column=4, value=int(concepto.valor)).number_format = _PESOS

    fila += 2
    hoja.cell(row=fila, column=1, value="TOTAL DEVENGADO").font = _NEGRITA
    celda_total = hoja.cell(row=fila, column=4, value=int(le.liquidacion.total))
    celda_total.font = _NEGRITA
    celda_total.number_format = _PESOS

    hoja.column_dimensions["A"].width = 42
    for col in "BCDE":
        hoja.column_dimensions[col].width = 14


def _hoja_resumen(hoja: Worksheet, liq: LiquidacionQuincena) -> None:
    _encabezado(hoja, liq)
    encabezados = ["EMPLEADO", "DOCUMENTO", "CARGO", "SALARIO MENSUAL", "TOTAL DEVENGADO"]
    fila = 5
    for col, texto in enumerate(encabezados, start=1):
        celda = hoja.cell(row=fila, column=col, value=texto)
        celda.font = _NEGRITA
        celda.border = _BORDE_FINO

    for le in liq.por_empleado:
        fila += 1
        hoja.cell(row=fila, column=1, value=le.empleado.nombre)
        hoja.cell(row=fila, column=2, value=le.empleado.documento)
        hoja.cell(row=fila, column=3, value=le.empleado.cargo)
        hoja.cell(row=fila, column=4, value=int(le.liquidacion.salario_mensual)).number_format = _PESOS
        hoja.cell(row=fila, column=5, value=int(le.liquidacion.total)).number_format = _PESOS

    fila += 2
    hoja.cell(row=fila, column=1, value="TOTAL UNIDAD").font = _NEGRITA
    celda = hoja.cell(row=fila, column=5, value=int(liq.total))
    celda.font = _NEGRITA
    celda.number_format = _PESOS

    hoja.column_dimensions["A"].width = 34
    for col in range(2, 6):
        hoja.column_dimensions[get_column_letter(col)].width = 18
    hoja["A1"].alignment = Alignment(horizontal="left")


def exportar_liquidacion_excel(liq: LiquidacionQuincena) -> bytes:
    libro = Workbook()
    resumen = libro.active
    resumen.title = "RESUMEN"
    _hoja_resumen(resumen, liq)
    for le in liq.por_empleado:
        hoja = libro.create_sheet(_titulo_hoja(le.empleado.nombre))
        _hoja_empleado(hoja, liq, le)

    contenido = BytesIO()
    libro.save(contenido)
    return contenido.getvalue()
