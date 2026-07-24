"""Flujo completo por la API HTTP: el camino que recorrerá la contadora."""


def test_flujo_completo_de_liquidacion(client):
    unidad = client.post(
        "/unidades", json={"nombre": "Edificio Thunapa P.H.", "nit": "800254433"}
    ).json()

    r = client.post(
        "/empleados",
        json={
            "unidad_id": unidad["id"],
            "nombre": "FREDY ALONSO HURTADO",
            "documento": "71712119",
            "cargo": "vigilante",
            "salario_base": 2_200_000,
        },
    )
    assert r.status_code == 201, r.text
    empleado = r.json()

    periodo = client.post(
        "/periodos", json={"fecha_inicio": "2026-06-16", "fecha_fin": "2026-06-30"}
    ).json()

    r = client.post(
        "/turnos",
        json={
            "empleado_id": empleado["id"],
            "fecha": "2026-06-28",
            "hora_inicio": "18:00",
            "hora_fin": "06:00",
        },
    )
    assert r.status_code == 201, r.text
    assert r.json()["cruza_medianoche"] is True

    r = client.post(f"/periodos/{periodo['id']}/liquidar", json={"unidad_id": unidad["id"]})
    assert r.status_code == 201, r.text
    liquidacion = r.json()
    assert liquidacion["version"] == 1
    assert liquidacion["total"] == 1_479_048
    conceptos = {c["codigo"]: c for c in liquidacion["empleados"][0]["conceptos"]}
    assert conceptos["festivo_nocturno"]["valor"] == 236_500
    assert conceptos["festivo_nocturno"]["factor"] == "2.15"
    assert conceptos["festivo_nocturno"]["horas"] == "11.00"

    # recuperable después
    r = client.get(f"/liquidaciones/{liquidacion['id']}")
    assert r.status_code == 200
    assert r.json()["total"] == 1_479_048

    # grilla del periodo
    turnos = client.get(f"/periodos/{periodo['id']}/turnos").json()
    assert len(turnos) == 1


def test_validaciones_de_turnos(client):
    unidad = client.post("/unidades", json={"nombre": "Unidad B"}).json()
    empleado = client.post(
        "/empleados",
        json={
            "unidad_id": unidad["id"],
            "nombre": "ANA",
            "documento": "123456",
            "cargo": "aseo",
            "salario_base": 1_750_905,
        },
    ).json()
    client.post("/periodos", json={"fecha_inicio": "2026-07-01", "fecha_fin": "2026-07-15"})

    base = {"empleado_id": empleado["id"], "fecha": "2026-07-02"}
    assert client.post(
        "/turnos", json=base | {"hora_inicio": "06:00", "hora_fin": "18:00"}
    ).status_code == 201
    # solapado → 409
    r = client.post("/turnos", json=base | {"hora_inicio": "17:00", "hora_fin": "23:00"})
    assert r.status_code == 409
    # fuera de todo periodo → 409
    r = client.post(
        "/turnos",
        json={"empleado_id": empleado["id"], "fecha": "2026-09-01",
              "hora_inicio": "06:00", "hora_fin": "18:00"},
    )
    assert r.status_code == 409
    # empleado inexistente → 404
    r = client.post(
        "/turnos",
        json={"empleado_id": "00000000-0000-0000-0000-000000000000",
              "fecha": "2026-07-02", "hora_inicio": "06:00", "hora_fin": "18:00"},
    )
    assert r.status_code == 404
    # documento no numérico → 422 (Pydantic)
    r = client.post(
        "/empleados",
        json={"unidad_id": unidad["id"], "nombre": "X", "documento": "abc",
              "cargo": "aseo", "salario_base": 1},
    )
    assert r.status_code == 422


def test_descuento_seguridad_social_y_conceptos_manuales(client):
    # Unidad que descuenta seguridad social, con estrategia 'diaria'.
    unidad = client.post(
        "/unidades",
        json={
            "nombre": "EDIFICIO CON DESCUENTO P.H.",
            "nit": "811001922",
            "descuenta_seguridad_social": True,
            "config": {"estrategia_extras": "diaria", "factores_override": {}},
        },
    ).json()
    assert unidad["descuenta_seguridad_social"] is True
    assert unidad["config"]["estrategia_extras"] == "diaria"

    empleado = client.post(
        "/empleados",
        json={"unidad_id": unidad["id"], "nombre": "MARIA", "documento": "43623487",
              "cargo": "aseo", "salario_base": 1_750_905},
    ).json()
    periodo = client.post(
        "/periodos", json={"fecha_inicio": "2026-07-01", "fecha_fin": "2026-07-15"}
    ).json()
    client.post(
        "/turnos",
        json={"empleado_id": empleado["id"], "fecha": "2026-07-02",
              "hora_inicio": "06:00", "hora_fin": "18:00"},  # 12h → 4 extra (diaria)
    )
    # Conceptos manuales: cuota de manejo (devengado no salarial) y un préstamo (deducción).
    cuota = client.post(
        "/conceptos-manuales",
        json={"empleado_id": empleado["id"], "periodo_id": periodo["id"],
              "tipo": "devengado", "nombre": "CUOTA DE MANEJO TARJETA",
              "valor": 7095, "salarial": False},
    )
    assert cuota.status_code == 201, cuota.text
    client.post(
        "/conceptos-manuales",
        json={"empleado_id": empleado["id"], "periodo_id": periodo["id"],
              "tipo": "deduccion", "nombre": "PRÉSTAMO", "valor": 50000, "salarial": False},
    )

    liq = client.post(f"/periodos/{periodo['id']}/liquidar", json={"unidad_id": unidad["id"]}).json()
    emp = liq["empleados"][0]
    ded = {d["codigo"]: d["valor"] for d in emp["deducciones"]}
    assert "aporte_salud" in ded and "aporte_pension" in ded
    assert ded["aporte_salud"] == ded["aporte_pension"]  # 4% == 4%
    assert emp["total_deducciones"] == sum(d["valor"] for d in emp["deducciones"])
    assert emp["neto_a_pagar"] == emp["total_devengado"] - emp["total_deducciones"]
    assert any(d["nombre"] == "PRÉSTAMO" and d["valor"] == 50000 for d in emp["deducciones"])
    assert any(c["nombre"] == "CUOTA DE MANEJO TARJETA" for c in emp["conceptos"])

    # PATCH: apagar el descuento → reliquidar deja solo las deducciones manuales.
    client.patch(f"/unidades/{unidad['id']}", json={"descuenta_seguridad_social": False})
    liq2 = client.post(f"/periodos/{periodo['id']}/liquidar", json={"unidad_id": unidad["id"]}).json()
    ded2 = {d["codigo"] for d in liq2["empleados"][0]["deducciones"]}
    assert "aporte_salud" not in ded2
    assert liq2["empleados"][0]["deducciones"][0]["nombre"] == "PRÉSTAMO"


def test_conceptos_fijos_por_unidad_se_aplican_solos(client):
    # Unidad con un concepto fijo (cuota de manejo) que se aplica a TODOS sus empleados.
    unidad = client.post(
        "/unidades",
        json={
            "nombre": "UNIDAD CON CUOTA FIJA P.H.",
            "config": {
                "estrategia_extras": None,
                "factores_override": {},
                "conceptos_fijos": [
                    {"nombre": "CUOTA DE MANEJO TARJETA", "valor": 7095,
                     "tipo": "devengado", "salarial": False},
                ],
            },
        },
    ).json()
    assert unidad["config"]["conceptos_fijos"][0]["valor"] == 7095

    empleado = client.post(
        "/empleados",
        json={"unidad_id": unidad["id"], "nombre": "PEDRO", "documento": "999888",
              "cargo": "todero", "salario_base": 1_750_905},
    ).json()
    periodo = client.post(
        "/periodos", json={"fecha_inicio": "2026-07-01", "fecha_fin": "2026-07-15"}
    ).json()
    client.post(
        "/turnos",
        json={"empleado_id": empleado["id"], "fecha": "2026-07-02",
              "hora_inicio": "06:00", "hora_fin": "14:00"},
    )
    # Sin crear ningún concepto manual, la cuota aparece en la liquidación.
    liq = client.post(f"/periodos/{periodo['id']}/liquidar", json={"unidad_id": unidad["id"]}).json()
    conceptos = liq["empleados"][0]["conceptos"]
    cuota = next(c for c in conceptos if c["nombre"] == "CUOTA DE MANEJO TARJETA")
    assert cuota["valor"] == 7095


def test_parametros_y_festivos(client):
    # historial sembrado y filtro por fecha
    todos = client.get("/parametros").json()
    assert len(todos) == 23
    vigentes = client.get("/parametros", params={"fecha": "2026-07-13"}).json()
    dominical = next(p for p in vigentes if p["codigo"] == "recargo_dominical_festivo")
    assert dominical["valor"] == "0.90"

    # nueva vigencia sin tocar código
    r = client.post(
        "/parametros",
        json={"codigo": "auxilio_transporte_mensual", "valor": "260000",
              "vigente_desde": "2027-01-01", "norma": "decreto 2027"},
    )
    assert r.status_code == 201
    r = client.post(
        "/parametros",
        json={"codigo": "no_existe", "valor": "1", "vigente_desde": "2027-01-01"},
    )
    assert r.status_code == 409

    # festivos: 2026 trae 18 por ley; agregar uno manual y anular otro
    assert len(client.get("/festivos/2026").json()) == 18
    client.put("/festivos", json={"fecha": "2026-06-17", "nombre": "día cívico"})
    client.put("/festivos", json={"fecha": "2026-06-29", "nombre": "", "es_festivo": False})
    festivos = client.get("/festivos/2026").json()
    fechas = {f["fecha"] for f in festivos}
    assert "2026-06-17" in fechas and "2026-06-29" not in fechas


def test_reabrir_periodo(client):
    unidad = client.post("/unidades", json={"nombre": "Unidad C"}).json()
    client.post(
        "/empleados",
        json={"unidad_id": unidad["id"], "nombre": "LUIS", "documento": "999999",
              "cargo": "todero", "salario_base": 2_000_000},
    )
    periodo = client.post(
        "/periodos", json={"fecha_inicio": "2026-08-01", "fecha_fin": "2026-08-15"}
    ).json()
    client.post(f"/periodos/{periodo['id']}/liquidar", json={"unidad_id": unidad["id"]})

    assert client.get("/periodos").json()[0]["estado"] == "liquidado"
    r = client.post(f"/periodos/{periodo['id']}/reabrir")
    assert r.status_code == 200 and r.json()["estado"] == "abierto"
