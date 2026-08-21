"""Flujo completo por la API HTTP: el camino que recorrerá la contadora."""

from uuid import uuid4

from nomina.semilla import PARAMETROS_SEMILLA


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

    # se puede borrar una liquidación; luego ya no es recuperable
    r = client.delete(f"/liquidaciones/{liquidacion['id']}")
    assert r.status_code == 204, r.text
    assert client.get(f"/liquidaciones/{liquidacion['id']}").status_code == 404
    assert client.get(f"/liquidaciones?periodo_id={periodo['id']}").json() == []
    # borrar una liquidación inexistente responde 404
    assert client.delete(f"/liquidaciones/{liquidacion['id']}").status_code == 404


def test_ocasional_sin_auxilio_de_transporte(client):
    unidad = client.post("/unidades", json={"nombre": "Edificio Ocasional P.H."}).json()
    empleado = client.post(
        "/empleados",
        json={
            "unidad_id": unidad["id"],
            "nombre": "ANA OCASIONAL",
            "documento": "71712121",
            "cargo": "aseo",
            "salario_base": 2_200_000,
        },
    ).json()
    assert empleado["ocasional"] is False
    periodo = client.post(
        "/periodos", json={"fecha_inicio": "2026-09-01", "fecha_fin": "2026-09-15"}
    ).json()
    client.post(
        "/turnos",
        json={
            "empleado_id": empleado["id"],
            "fecha": "2026-09-03",
            "hora_inicio": "06:00",
            "hora_fin": "14:00",
        },
    )

    liq = client.post(f"/periodos/{periodo['id']}/liquidar", json={"unidad_id": unidad["id"]}).json()
    assert "auxilio_transporte" in {c["codigo"] for c in liq["empleados"][0]["conceptos"]}

    r = client.patch(f"/empleados/{empleado['id']}", json={"ocasional": True})
    assert r.status_code == 200
    assert r.json()["ocasional"] is True

    liq2 = client.post(f"/periodos/{periodo['id']}/liquidar", json={"unidad_id": unidad["id"]}).json()
    assert "auxilio_transporte" not in {c["codigo"] for c in liq2["empleados"][0]["conceptos"]}


def test_incapacitado_sin_auxilio_y_quincena_incompleta_por_horas_trabajadas(client):
    unidad = client.post("/unidades", json={"nombre": "Edificio Incapacidad P.H."}).json()
    empleado = client.post(
        "/empleados",
        json={
            "unidad_id": unidad["id"],
            "nombre": "JUAN INCAPACITADO",
            "documento": "71712120",
            "cargo": "vigilante",
            "salario_base": 2_200_000,
        },
    ).json()
    assert empleado["incapacitado"] is False
    periodo = client.post(
        "/periodos", json={"fecha_inicio": "2026-08-01", "fecha_fin": "2026-08-15"}
    ).json()
    client.post(
        "/turnos",
        json={
            "empleado_id": empleado["id"],
            "fecha": "2026-08-03",
            "hora_inicio": "06:00",
            "hora_fin": "14:00",
        },
    )

    # Sin marcar nada: comportamiento actual (auxilio incluido, ordinario al tope legal).
    r = client.get("/ajustes-quincena", params={"empleado_id": empleado["id"], "periodo_id": periodo["id"]})
    assert r.status_code == 200
    assert r.json()["quincena_incompleta"] is False

    liq = client.post(f"/periodos/{periodo['id']}/liquidar", json={"unidad_id": unidad["id"]}).json()
    conceptos = {c["codigo"]: c for c in liq["empleados"][0]["conceptos"]}
    assert "auxilio_transporte" in conceptos
    # ago-2026: 105 h × (2.200.000/210) = salario/2. El par horas/divisor va junto.
    assert conceptos["tiempo_ordinario"]["valor"] == 1_100_000

    # Se marca incapacitado + quincena incompleta.
    r = client.patch(f"/empleados/{empleado['id']}", json={"incapacitado": True})
    assert r.status_code == 200
    assert r.json()["incapacitado"] is True

    r = client.put(
        "/ajustes-quincena",
        params={"empleado_id": empleado["id"], "periodo_id": periodo["id"]},
        json={"quincena_incompleta": True},
    )
    assert r.status_code == 200
    assert r.json()["quincena_incompleta"] is True

    liq2 = client.post(f"/periodos/{periodo['id']}/liquidar", json={"unidad_id": unidad["id"]}).json()
    assert liq2["version"] == 2
    conceptos2 = {c["codigo"]: c for c in liq2["empleados"][0]["conceptos"]}
    assert "auxilio_transporte" not in conceptos2
    # divisor vigente en ago-2026 es 210 (post 15-jul-2026): 2.200.000/210 × 8 h
    assert conceptos2["tiempo_ordinario"]["valor"] == 83_810


def test_auxilio_prorrateado_manda_sobre_incapacitado(client):
    """El empleado se incapacitó a mitad de quincena pero alcanzó a trabajar unas
    horas: marcar el prorrateo le devuelve el auxilio, proporcional a lo laborado,
    aunque estar incapacitado normalmente se lo quite entero."""
    unidad = client.post("/unidades", json={"nombre": "Edificio Prorrateo P.H."}).json()
    empleado = client.post(
        "/empleados",
        json={
            "unidad_id": unidad["id"],
            "nombre": "LUZ PRORRATEO",
            "documento": "71712122",
            "cargo": "aseo",
            "salario_base": 2_200_000,
        },
    ).json()
    periodo = client.post(
        "/periodos", json={"fecha_inicio": "2026-08-01", "fecha_fin": "2026-08-15"}
    ).json()
    # 24 h laboradas en total (el día 5 es turno partido: 4 h + 4 h).
    for fecha, inicio, fin in [
        ("2026-08-03", "06:00", "14:00"),
        ("2026-08-04", "06:00", "14:00"),
        ("2026-08-05", "06:00", "10:00"),
        ("2026-08-05", "12:00", "16:00"),
    ]:
        r = client.post(
            "/turnos",
            json={
                "empleado_id": empleado["id"],
                "fecha": fecha,
                "hora_inicio": inicio,
                "hora_fin": fin,
            },
        )
        assert r.status_code == 201, r.text

    # El flag arranca apagado aunque no exista fila de ajustes.
    r = client.get(
        "/ajustes-quincena",
        params={"empleado_id": empleado["id"], "periodo_id": periodo["id"]},
    )
    assert r.json()["auxilio_por_dias_laborados"] is False

    client.patch(f"/empleados/{empleado['id']}", json={"incapacitado": True})
    liq = client.post(
        f"/periodos/{periodo['id']}/liquidar", json={"unidad_id": unidad["id"]}
    ).json()
    assert "auxilio_transporte" not in {c["codigo"] for c in liq["empleados"][0]["conceptos"]}

    r = client.put(
        "/ajustes-quincena",
        params={"empleado_id": empleado["id"], "periodo_id": periodo["id"]},
        json={"auxilio_por_dias_laborados": True},
    )
    assert r.status_code == 200
    assert r.json()["auxilio_por_dias_laborados"] is True
    # No pisa los flags hermanos.
    assert r.json()["quincena_incompleta"] is False
    assert r.json()["sin_extras"] is False

    liq2 = client.post(
        f"/periodos/{periodo['id']}/liquidar", json={"unidad_id": unidad["id"]}
    ).json()
    auxilio = next(
        c for c in liq2["empleados"][0]["conceptos"] if c["codigo"] == "auxilio_transporte"
    )
    # 24 h laboradas, divisor 210 (ago-2026): 249.095 × 24 / 210 = 28.468
    assert auxilio["valor"] == 28_468
    assert auxilio["componentes"] == {"horas_laboradas": "24"}


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


def test_coherencia_de_parametros(client):
    """El par horas/divisor sembrado cuadra; descuadrarlo lo delata el endpoint."""
    assert client.get("/parametros/coherencia").json() == []

    # Bajar el divisor a 210 sin bajar las horas a 105: el error real de agosto-2026.
    r = client.post("/parametros", json={
        "codigo": "divisor_hora_ordinaria", "valor": "999",
        "vigente_desde": "2027-01-01", "norma": "prueba"})
    assert r.status_code == 201, r.text

    (aviso,) = client.get("/parametros/coherencia").json()
    assert aviso["desde"] == "2027-01-01"
    assert aviso["hasta"] is None
    assert "999" in aviso["detalle"]


def test_parametros_y_festivos(client):
    # historial sembrado y filtro por fecha
    todos = client.get("/parametros").json()
    assert len(todos) == len(PARAMETROS_SEMILLA)
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

    # liquidar una unidad no cierra el periodo: sigue abierto
    assert client.get("/periodos").json()[0]["estado"] == "abierto"

    # marcar todo el periodo como liquidado es un paso explícito
    m = client.post(f"/periodos/{periodo['id']}/liquidar-periodo")
    assert m.status_code == 200 and m.json()["estado"] == "liquidado"

    r = client.post(f"/periodos/{periodo['id']}/reabrir")
    assert r.status_code == 200 and r.json()["estado"] == "abierto"


def test_jornada_ordinaria_por_turno(client):
    """La casilla «jornada ordinaria» se marca por turno con un PATCH: el turno
    de domingo deja de pagar festivo y solo se reconoce el excedente del umbral."""
    unidad = client.post("/unidades", json={"nombre": "Edificio Jornada P.H."}).json()
    empleado = client.post(
        "/empleados",
        json={
            "unidad_id": unidad["id"],
            "nombre": "ANA JORNADA",
            "documento": "71712121",
            "cargo": "vigilante",
            "salario_base": 2_200_000,
        },
    ).json()
    periodo = client.post(
        "/periodos", json={"fecha_inicio": "2026-08-01", "fecha_fin": "2026-08-15"}
    ).json()
    # domingo 2-ago-2026, 06:00-16:00 = 10 h dominicales
    turno = client.post(
        "/turnos",
        json={
            "empleado_id": empleado["id"],
            "fecha": "2026-08-02",
            "hora_inicio": "06:00",
            "hora_fin": "16:00",
        },
    ).json()
    assert turno["minutos_jornada_ordinaria"] is None

    liq = client.post(f"/periodos/{periodo['id']}/liquidar", json={"unidad_id": unidad["id"]}).json()
    assert "festivo_diurno" in {c["codigo"] for c in liq["empleados"][0]["conceptos"]}

    # Marcada la jornada ordinaria en 7 h: solo las 3 h de más se reconocen.
    r = client.patch(
        f"/turnos/{turno['id']}/jornada-ordinaria", json={"minutos_jornada_ordinaria": 420}
    )
    assert r.status_code == 200
    assert r.json()["minutos_jornada_ordinaria"] == 420

    liq2 = client.post(f"/periodos/{periodo['id']}/liquidar", json={"unidad_id": unidad["id"]}).json()
    conceptos = {c["codigo"]: c for c in liq2["empleados"][0]["conceptos"]}
    assert "festivo_diurno" not in conceptos
    assert conceptos["extra_diurna_festiva"]["minutos"] == 180

    # Desmarcar (null) vuelve al comportamiento original.
    r = client.patch(
        f"/turnos/{turno['id']}/jornada-ordinaria", json={"minutos_jornada_ordinaria": None}
    )
    assert r.status_code == 200
    assert r.json()["minutos_jornada_ordinaria"] is None
    liq3 = client.post(f"/periodos/{periodo['id']}/liquidar", json={"unidad_id": unidad["id"]}).json()
    assert "festivo_diurno" in {c["codigo"] for c in liq3["empleados"][0]["conceptos"]}


def test_jornada_ordinaria_rechaza_turno_inexistente_y_periodo_cerrado(client):
    unidad = client.post("/unidades", json={"nombre": "Edificio Cerrado P.H."}).json()
    empleado = client.post(
        "/empleados",
        json={
            "unidad_id": unidad["id"],
            "nombre": "LUIS CERRADO",
            "documento": "71712122",
            "cargo": "vigilante",
            "salario_base": 2_200_000,
        },
    ).json()
    periodo = client.post(
        "/periodos", json={"fecha_inicio": "2026-09-01", "fecha_fin": "2026-09-15"}
    ).json()
    turno = client.post(
        "/turnos",
        json={
            "empleado_id": empleado["id"],
            "fecha": "2026-09-06",
            "hora_inicio": "06:00",
            "hora_fin": "16:00",
            "minutos_jornada_ordinaria": 420,
        },
    ).json()
    assert turno["minutos_jornada_ordinaria"] == 420

    assert client.patch(
        f"/turnos/{uuid4()}/jornada-ordinaria", json={"minutos_jornada_ordinaria": 420}
    ).status_code == 404

    # umbral no positivo: lo rechaza el schema
    assert client.patch(
        f"/turnos/{turno['id']}/jornada-ordinaria", json={"minutos_jornada_ordinaria": 0}
    ).status_code == 422

    client.post(f"/periodos/{periodo['id']}/liquidar", json={"unidad_id": unidad["id"]})
    client.post(f"/periodos/{periodo['id']}/liquidar-periodo")
    r = client.patch(
        f"/turnos/{turno['id']}/jornada-ordinaria", json={"minutos_jornada_ordinaria": 300}
    )
    assert r.status_code == 400
