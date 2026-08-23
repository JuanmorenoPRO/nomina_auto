#!/usr/bin/env python3
"""Regenera las capturas de `docs/manual-usuario.md` con Playwright.

Las imágenes salen de la base de DEMOSTRACIÓN (`nomina/demo.py`), con nombres y
cédulas ficticios: nunca se capturan datos reales de empleados.

Preparación (una sola vez):

    cd backend
    export DATABASE_URL=sqlite:///./nomina_demo.sqlite3
    export NOMINA_ADMIN_PASSWORD='...'          # mínimo 10 caracteres
    uv run alembic upgrade head
    uv run python -m nomina.infraestructura.persistencia.sembrar_demo

    cd ../frontend && npm run build

Levantar la app (el backend sirve la SPA, así no hace falta el proxy de Vite):

    cd backend
    DATABASE_URL=sqlite:///./nomina_demo.sqlite3 \
    STATIC_DIR=../frontend/dist \
      uv run uvicorn nomina.infraestructura.api.app:crear_app --factory --port 8011

Y por último, desde la raíz del repo:

    NOMINA_ADMIN_PASSWORD='...' python3 scripts/capturar-manual.py

Variables opcionales: NOMINA_DEMO_URL (por defecto http://127.0.0.1:8011),
NOMINA_DEMO_EMAIL (por defecto demo@ejemplo.com).
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

from playwright.sync_api import Locator, Page, sync_playwright

RAIZ = Path(__file__).resolve().parent.parent
SALIDA = RAIZ / "docs" / "imagenes"

URL = os.environ.get("NOMINA_DEMO_URL", "http://127.0.0.1:8011")
EMAIL = os.environ.get("NOMINA_DEMO_EMAIL", "demo@ejemplo.com")
CLAVE = os.environ.get("NOMINA_ADMIN_PASSWORD", "")

ANCHO = 1440
ALTO = 900

UNIDAD = "CONJUNTO LOS ALMENDROS P.H"
QUINCENA = "2026-08-01 al 2026-08-15 (abierto)"
QUINCENA_CERRADA = "2026-07-01 al 2026-07-15 (cerrado)"
EMPLEADO_NOCTURNO = "Marcela Osorio Ríos"
EMPLEADO_PARTIDO = "Hernán Duque Salazar"
EMPLEADO_JORNADA = "Lucía Cardona Vélez"
EMPLEADO_PARCIAL = "Andrés Peláez Mesa"


# --- utilidades ------------------------------------------------------------ #


def guardar(objetivo: Page | Locator, nombre: str, **kwargs) -> None:
    objetivo.screenshot(path=str(SALIDA / nombre), **kwargs)
    print(f"  ✓ {nombre}")


def guardar_pagina(page: Page, nombre: str, margen: int = 24) -> None:
    """Captura la ventana recortada al contenido: evita el vacío de abajo."""
    alto = page.evaluate(
        "() => { const m = document.querySelector('main');"
        " return m ? Math.ceil(m.getBoundingClientRect().bottom) : document.body.scrollHeight; }"
    )
    ancho, alto_ventana = page.viewport_size["width"], page.viewport_size["height"]
    guardar(
        page,
        nombre,
        clip={"x": 0, "y": 0, "width": ancho, "height": min(alto + margen, alto_ventana)},
    )


def ventana(page: Page, ancho: int = ANCHO, alto: int = ALTO) -> None:
    page.set_viewport_size({"width": ancho, "height": alto})
    page.wait_for_timeout(300)


def ir_a(page: Page, pestana: str) -> None:
    page.get_by_role("button", name=pestana, exact=True).click()
    page.wait_for_timeout(500)


def tarjeta(page: Page, titulo: str) -> Locator:
    return page.locator(".tarjeta").filter(
        has=page.get_by_role("heading", name=titulo, exact=True)
    )


_CAJA_SECCION = """(datos) => {
    const encabezados = [...document.querySelectorAll('main h2')];
    const i = encabezados.findIndex((h) => h.textContent.trim() === datos.titulo);
    if (i < 0) return null;
    const main = document.querySelector('main').getBoundingClientRect();
    const y = encabezados[i].getBoundingClientRect().top + window.scrollY - 12;
    const fin = encabezados[i + 1]
        ? encabezados[i + 1].getBoundingClientRect().top + window.scrollY - 16
        : main.bottom + window.scrollY + 8;
    return {
        x: Math.max(main.left - 12, 0),
        y,
        width: Math.min(main.width + 24, window.innerWidth),
        height: Math.min(fin - y, datos.alto),
    };
}"""


def guardar_seccion(page: Page, titulo: str, nombre: str, alto_max: int = 4000) -> None:
    """Recorta desde un `<h2>` hasta el siguiente: las secciones de Configuración
    no están envueltas en `.tarjeta`, así que no hay un elemento que capturar."""
    caja = page.evaluate(_CAJA_SECCION, {"titulo": titulo, "alto": alto_max})
    if caja is None:
        raise RuntimeError(f"No se encontró la sección «{titulo}»")
    guardar(page, nombre, full_page=True, clip=caja)


def abrir_cuadro_de_turnos(page: Page) -> None:
    ir_a(page, "Cuadro de turnos")
    page.get_by_label("Unidad residencial").select_option(label=UNIDAD)
    page.get_by_label("Quincena").select_option(label=QUINCENA)
    page.wait_for_selector("table.grilla tbody tr")
    page.wait_for_timeout(500)


def abrir_previa(page: Page, empleado: str) -> None:
    page.locator("td.nombre-empleado", has_text=empleado).locator("button.boton-previa").click()
    page.wait_for_selector(".modal-previa")
    page.wait_for_timeout(500)


def cerrar_previa(page: Page) -> None:
    page.get_by_role("button", name="Cancelar").click()
    page.wait_for_timeout(400)


def fila_dia(page: Page, numero: int) -> Locator:
    """Fila de la tarjeta de turnos del día `numero` del mes."""
    return page.locator("table.tarjeta-turnos tbody tr").filter(
        has=page.locator(f"td.num-dia:text-is('{numero}')")
    )


def bloque_empleado(page: Page, empleado: str) -> Locator:
    """El `div` con el encabezado y la tabla de conceptos de un empleado."""
    return page.locator("h3", has_text=empleado).locator("xpath=..")


# --- guion de capturas ----------------------------------------------------- #


def capturar(page: Page) -> None:
    # 1. Ingreso ------------------------------------------------------------ #
    page.goto(URL, wait_until="networkidle")
    page.wait_for_selector("input[type=email]")
    page.fill("input[type=email]", EMAIL)
    page.fill("input[type=password]", CLAVE)
    page.wait_for_timeout(250)
    guardar_pagina(page, "01-login.png")

    page.get_by_role("button", name="Ingresar").click()
    page.wait_for_selector("nav.pestanas", timeout=15_000)
    page.wait_for_timeout(700)

    # 2-3. Cuadro de turnos -------------------------------------------------- #
    # La grilla es ancha (15 días): se ensancha la ventana para que quepa entera.
    ventana(page, ANCHO, 780)
    abrir_cuadro_de_turnos(page)
    guardar_pagina(page, "02-cuadro-turnos.png")

    # La grilla no cabe entera (el contenedor va a 1280 px y la tabla scrollea):
    # segunda toma con el scroll al final, donde está la columna «Total h».
    page.locator(".grilla-envoltura").evaluate("el => { el.scrollLeft = el.scrollWidth; }")
    page.wait_for_timeout(400)
    guardar_pagina(page, "03-cuadro-turnos-final.png")

    # Recorte de una fila: chips, botón ×, input «hh-hh» y casilla «ord.».
    page.locator(".grilla-envoltura").evaluate("el => { el.scrollLeft = 0; }")
    page.wait_for_timeout(300)
    guardar(
        page.locator("table.grilla tbody tr", has_text=EMPLEADO_JORNADA),
        "04-grilla-fila.png",
    )

    # 4-11. Previsualización -------------------------------------------------- #
    # El modal es alto: la ventana crece para que quepa sin recortarse.
    ventana(page, 1200, 1500)
    abrir_previa(page, EMPLEADO_NOCTURNO)
    guardar(page.locator(".modal-previa"), "05-previa-completa.png")
    guardar(page.locator(".previa-encabezado"), "06-previa-encabezado.png")
    guardar(page.locator(".previa-estados"), "07-previa-estados.png")
    guardar(
        page.locator(".modal-previa div.fila").filter(has_text="No laboró todas las horas"),
        "08-previa-ajustes.png",
    )
    cerrar_previa(page)

    # La tarjeta del turno partido: dos líneas «Entra»/«Sale» el mismo día.
    abrir_previa(page, EMPLEADO_PARTIDO)
    guardar(fila_dia(page, 3), "09-previa-turno-partido.png")
    cerrar_previa(page)

    # Los dos casos de «jornada ordinaria»: el turno real del festivo (7) con
    # umbral, y el turno de relleno del sábado 8.
    abrir_previa(page, EMPLEADO_JORNADA)
    guardar(page.locator("table.tarjeta-turnos"), "10-previa-tabla.png")
    guardar(fila_dia(page, 7), "11-previa-jornada-ordinaria.png")
    guardar(fila_dia(page, 8), "12-previa-turno-relleno.png")
    cerrar_previa(page)

    # 12. Los tres ajustes ya marcados en el empleado de quincena incompleta.
    abrir_previa(page, EMPLEADO_PARCIAL)
    guardar(
        page.locator(".modal-previa div.fila").filter(has_text="No laboró todas las horas"),
        "13-previa-ajustes-marcados.png",
    )
    cerrar_previa(page)

    # Una acción real (registrar un turno y borrarlo) para que la pestaña de
    # auditoría tenga registros que mostrar. Deja los datos como estaban.
    celda = (
        page.locator("table.grilla tbody tr", has_text=EMPLEADO_PARCIAL)
        .locator("td.celda-turno")
        .first
    )
    entrada = celda.locator("input[placeholder='hh-hh']")
    entrada.fill("08:00-12:00")
    entrada.press("Enter")
    page.wait_for_timeout(900)
    celda.locator("span.chip button").first.click()
    page.wait_for_timeout(900)

    # 14. Modo solo lectura: una quincena ya cerrada no deja tocar los turnos.
    ventana(page, ANCHO, 780)
    page.get_by_label("Quincena").select_option(label=QUINCENA_CERRADA)
    page.wait_for_timeout(700)
    guardar_pagina(page, "14-cuadro-solo-lectura.png")

    # 15-16. Liquidación ------------------------------------------------------ #
    ventana(page, ANCHO, 1000)
    ir_a(page, "Liquidación")
    page.get_by_label("Quincena").select_option(label=QUINCENA)
    page.get_by_label("Unidad residencial").select_option(label=UNIDAD)
    page.wait_for_timeout(700)
    guardar_pagina(page, "15-liquidacion.png")

    page.get_by_role("button", name="Ver detalle").first.click()
    page.wait_for_timeout(800)
    guardar(bloque_empleado(page, EMPLEADO_NOCTURNO), "16-liquidacion-desglose.png")
    guardar(bloque_empleado(page, EMPLEADO_PARCIAL), "17-desglose-quincena-incompleta.png")

    # 16-19. Unidades y empleados ---------------------------------------------- #
    ir_a(page, "Unidades y empleados")
    page.wait_for_timeout(700)
    guardar(tarjeta(page, "Unidades residenciales"), "18-unidades.png")
    guardar(tarjeta(page, "Conceptos fijos por unidad"), "19-conceptos-fijos.png")
    guardar(tarjeta(page, "Empleados"), "20-empleados.png")
    guardar(
        tarjeta(page, "Conceptos manuales (por empleado y quincena)"),
        "21-conceptos-manuales.png",
    )
    guardar(tarjeta(page, "Periodos de liquidación (quincenas)"), "22-periodos.png")

    # 21-24. Configuración ------------------------------------------------------ #
    ir_a(page, "Configuración")
    page.wait_for_timeout(900)
    guardar_seccion(page, "Parámetros legales", "23-parametros.png", alto_max=1400)
    guardar_seccion(page, "Festivos", "24-festivos.png", alto_max=1400)
    guardar_seccion(page, "Usuarios", "25-usuarios.png")
    guardar_seccion(page, "Auditoría (últimos 100 registros)", "26-auditoria.png", alto_max=900)


def main() -> None:
    if len(CLAVE) < 10:
        sys.exit("Defina NOMINA_ADMIN_PASSWORD con la contraseña del usuario de la demo.")
    SALIDA.mkdir(parents=True, exist_ok=True)
    for viejo in SALIDA.glob("*.png"):
        viejo.unlink()
    with sync_playwright() as p:
        navegador = p.chromium.launch()
        contexto = navegador.new_context(
            viewport={"width": ANCHO, "height": ALTO},
            device_scale_factor=2,
            locale="es-CO",
            timezone_id="America/Bogota",
        )
        page = contexto.new_page()
        try:
            capturar(page)
        finally:
            contexto.close()
            navegador.close()
    print(f"\nCapturas en {SALIDA}")


if __name__ == "__main__":
    main()
