"""Exportación a Excel: el archivo que recibe la contadora."""

from datetime import UTC, date, datetime
from decimal import Decimal
from io import BytesIO
from uuid import uuid4

from openpyxl import load_workbook

from nomina.aplicacion.casos_uso.liquidar_quincena import (
    LiquidacionEmpleado,
    LiquidacionQuincena,
)
from nomina.dominio.entidades.concepto_liquidado import Liquidacion
from nomina.dominio.entidades.empleado import Empleado
from nomina.dominio.entidades.periodo_liquidacion import PeriodoLiquidacion
from nomina.dominio.entidades.unidad_residencial import UnidadResidencial
from nomina.infraestructura.excel.exportador import exportar_liquidacion_excel


def _preparar_liquidacion(client, incapacitado: tuple[str, ...] = ()) -> str:
    unidad = client.post(
        "/unidades", json={"nombre": "Edificio Thunapa P.H.", "nit": "800254433"}
    ).json()
    empleado = client.post(
        "/empleados",
        json={"unidad_id": unidad["id"], "nombre": "FREDY ALONSO HURTADO",
              "documento": "71712119", "cargo": "vigilante", "salario_base": 2_200_000},
    ).json()
    periodo = client.post(
        "/periodos", json={"fecha_inicio": "2026-06-16", "fecha_fin": "2026-06-30"}
    ).json()
    client.post(
        "/turnos",
        json={"empleado_id": empleado["id"], "fecha": "2026-06-28",
              "hora_inicio": "18:00", "hora_fin": "06:00"},
    )
    for fecha in incapacitado:
        r = client.put(
            "/novedades-dia",
            json={"empleado_id": empleado["id"], "fecha": fecha, "tipo": "incapacidad"},
        )
        assert r.status_code == 204, r.text
    r = client.post(f"/periodos/{periodo['id']}/liquidar", json={"unidad_id": unidad["id"]})
    return r.json()["id"]


def test_descarga_excel_con_desglose(client):
    liquidacion_id = _preparar_liquidacion(client)

    r = client.get(f"/liquidaciones/{liquidacion_id}/excel")
    assert r.status_code == 200
    assert "spreadsheetml" in r.headers["content-type"]
    assert 'filename="liquidacion_Edificio_Thunapa_P.H._2026-06-16_2026-06-30_v1.xlsx"' in (
        r.headers["content-disposition"]
    )

    libro = load_workbook(BytesIO(r.content))
    assert libro.sheetnames == ["RESUMEN", "FREDY ALONSO HURTADO"]

    resumen = libro["RESUMEN"]
    assert resumen["A1"].value == "Edificio Thunapa P.H."
    assert resumen["A6"].value == "FREDY ALONSO HURTADO"
    assert resumen["E5"].value == "INCAPACIDAD"
    assert resumen["F5"].value == "DIAS LAB"
    assert (resumen["E6"].value, resumen["F6"].value) == (0, 15)
    assert resumen["G6"].value == 1_479_048  # total devengado del empleado

    hoja = libro["FREDY ALONSO HURTADO"]
    filas = {
        hoja.cell(row=f, column=1).value: hoja.cell(row=f, column=3).value
        for f in range(9, 15)
    }
    assert filas["TIEMPO ORDINARIO"] == 1_100_000
    assert filas["TIEMPO FESTIVO"] == 18_000
    assert filas["TIEMPO NOCTURNO DOMINICAL/FESTIVO"] == 236_500
    assert filas["AUXILIO DE TRANSPORTE"] == 124_548
    # Fila del salario, como en la planilla: INCAPACIDAD n | DIAS LAB n.
    assert [hoja[c].value for c in ("D6", "E6", "F6", "G6")] == ["INCAPACIDAD", 0, "DIAS LAB", 15]


def test_excel_muestra_los_dias_incapacitados(client):
    """Incapacitado el 29 y el 30: INCAPACIDAD 2, DIAS LAB 13, en la hoja y el resumen."""
    liquidacion_id = _preparar_liquidacion(client, incapacitado=("2026-06-29", "2026-06-30"))
    libro = load_workbook(BytesIO(client.get(f"/liquidaciones/{liquidacion_id}/excel").content))

    hoja = libro["FREDY ALONSO HURTADO"]
    assert [hoja[c].value for c in ("D6", "E6", "F6", "G6")] == ["INCAPACIDAD", 2, "DIAS LAB", 13]
    assert hoja["D6"].font.color.rgb.endswith("FF0000")
    resumen = libro["RESUMEN"]
    assert (resumen["E6"].value, resumen["F6"].value) == (2, 13)


def test_liquidacion_anterior_sin_dias_deja_las_celdas_vacias():
    """Una liquidación guardada antes de este dato (None) no inventa los días."""
    unidad = UnidadResidencial(id=uuid4(), nombre="Edificio Viejo P.H.")
    empleado = Empleado(
        id=uuid4(), unidad_id=unidad.id, nombre="ANA VIEJA", documento="1",
        cargo="aseo", salario_base=Decimal(1_750_905),
    )
    liq = LiquidacionQuincena(
        id=uuid4(),
        periodo=PeriodoLiquidacion(id=uuid4(), fecha_inicio=date(2026, 6, 1),
                                   fecha_fin=date(2026, 6, 15)),
        unidad=unidad,
        version=1,
        creada_en=datetime.now(UTC),
        por_empleado=(
            LiquidacionEmpleado(
                empleado=empleado,
                liquidacion=Liquidacion(
                    salario_mensual=Decimal(1_750_905), tarifa_hora=Decimal(1), conceptos=()
                ),
            ),
        ),
    )
    libro = load_workbook(BytesIO(exportar_liquidacion_excel(liq)))
    hoja = libro["ANA VIEJA"]
    assert hoja["D6"].value == "INCAPACIDAD"
    assert hoja["E6"].value is None
    assert hoja["G6"].value is None
    assert libro["RESUMEN"]["E6"].value is None


def test_excel_de_liquidacion_inexistente(client):
    r = client.get("/liquidaciones/00000000-0000-0000-0000-000000000000/excel")
    assert r.status_code == 404
