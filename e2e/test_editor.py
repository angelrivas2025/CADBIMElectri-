"""Prueba E2E del editor web con Playwright.

No forma parte de la suite por defecto (``testpaths = core/tests``). Se ejecuta
con ``python -m pytest e2e -q`` y usa Edge o Chrome instalados; en su defecto,
``python -m playwright install chromium``.
"""
from __future__ import annotations

import json
import os
import socket
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

import pytest
from playwright.sync_api import (
    Error as PlaywrightError,
    expect,
    sync_playwright,
)

RAIZ = Path(__file__).resolve().parents[1]
CONFORME = RAIZ / "examples" / "casa-conforme.json"


def _puerto_libre() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def _lanzar_navegador(playwright):
    for opciones in ({"channel": "msedge"}, {"channel": "chrome"}, {}):
        try:
            return playwright.chromium.launch(headless=True, **opciones)
        except PlaywrightError:
            continue
    pytest.skip("Playwright no encontró un navegador; ejecute 'playwright install chromium'")


@pytest.fixture()
def servidor(tmp_path):
    puerto = _puerto_libre()
    salida = tmp_path / "salida"
    entorno = {**os.environ}
    entorno.pop("CADBIM_LLM_KEY", None)
    proceso = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "api",
            "--proyecto",
            str(CONFORME),
            "--port",
            str(puerto),
            "--salida",
            str(salida),
        ],
        cwd=RAIZ,
        env=entorno,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.STDOUT,
    )
    base = f"http://127.0.0.1:{puerto}"
    for _ in range(100):
        if proceso.poll() is not None:
            pytest.fail("el servidor de prueba terminó antes de responder")
        try:
            with urllib.request.urlopen(base + "/api/estado", timeout=1) as respuesta:
                if respuesta.status == 200:
                    break
        except OSError:
            time.sleep(0.1)
    else:
        proceso.terminate()
        pytest.fail("el servidor de prueba no respondió")
    yield base, salida
    proceso.terminate()
    try:
        proceso.wait(timeout=5)
    except subprocess.TimeoutExpired:
        proceso.kill()


def _artefactos() -> Path:
    destino = Path(os.environ.get("CADBIM_E2E_ARTIFACTS", "salida/e2e"))
    destino.mkdir(parents=True, exist_ok=True)
    return destino


def _estado(contexto, base):
    respuesta = contexto.request.get(base + "/api/estado")
    assert respuesta.status == 200
    return respuesta.json()


def _sin_errores_de_navegador(errores_pagina, errores_consola):
    assert errores_pagina == []
    relevantes = [
        texto
        for texto in errores_consola
        if "Failed to load resource" not in texto and "favicon" not in texto
    ]
    assert relevantes == []


def _captura(pagina, ruta: Path) -> None:
    """Captura la página sin el aviso flotante, que en la vista completa se
    superpone al contenido."""
    pagina.locator("#estado-linea").evaluate(
        "linea => linea.classList.remove('visible')"
    )
    pagina.screenshot(path=str(ruta), full_page=True)


def test_flujo_completo_del_editor(servidor):
    base, salida = servidor
    artefactos = _artefactos()
    errores_pagina: list[str] = []
    errores_consola: list[str] = []

    with sync_playwright() as playwright:
        navegador = _lanzar_navegador(playwright)
        contexto = navegador.new_context(viewport={"width": 1440, "height": 1100})
        pagina = contexto.new_page()
        pagina.set_default_timeout(15000)
        pagina.on("pageerror", lambda error: errores_pagina.append(str(error)))
        pagina.on(
            "console",
            lambda mensaje: (
                errores_consola.append(mensaje.text)
                if mensaje.type == "error"
                else None
            ),
        )

        pagina.goto(base, wait_until="networkidle")
        expect(pagina.locator("#proyecto-nombre")).to_contain_text("Casa simple")
        expect(pagina.locator("polygon.ambiente")).to_have_count(3)
        expect(pagina.locator(".punto:not(.seleccion-preview)")).to_have_count(14)
        expect(pagina.locator("#veredicto")).to_contain_text("Conforme")
        expect(pagina.locator("#tabla-circuitos tr")).to_have_count(3)
        primera_fila = pagina.locator("#tabla-circuitos tr").first
        expect(primera_fila).to_contain_text("C1")
        expect(primera_fila).to_contain_text("1,5")

        # Nombre y área de cada ambiente deben quedar en renglones separados.
        solapadas = pagina.evaluate(
            """() => {
              const nombres = [...document.querySelectorAll(
                '.nombre-ambiente:not(.detalle)')];
              const areas = [...document.querySelectorAll(
                '.nombre-ambiente.detalle')];
              return nombres.filter((n, i) => {
                const a = n.getBBox();
                const b = areas[i].getBBox();
                return a.y + a.height > b.y + 0.01;
              }).length;
            }"""
        )
        assert solapadas == 0

        # Colocar un punto con un clic dentro del primer ambiente.
        caja = pagina.locator("polygon.ambiente").first.bounding_box()
        assert caja is not None
        pagina.mouse.click(caja["x"] + caja["width"] / 2, caja["y"] + caja["height"] / 2)
        expect(pagina.locator("#btn-punto")).to_be_enabled()
        expect(pagina.locator("#pista-punto")).to_contain_text("dentro de Sala")
        pagina.select_option("#punto-tipo", "tug")
        pagina.fill("#punto-potencia", "250")
        pagina.click("#btn-punto")
        expect(pagina.locator("#estado-linea")).to_contain_text("Punto P15 agregado")
        expect(pagina.locator(".punto:not(.seleccion-preview)")).to_have_count(15)
        punto = next(
            p for p in _estado(contexto, base)["proyecto"]["points"] if p["id"] == "P15"
        )
        assert punto["power"] == 250
        assert punto["room"] == "R1"
        assert 0 <= punto["position"][0] <= 4
        assert 0 <= punto["position"][1] <= 3.5

        # Deshacer devuelve el proyecto al estado anterior.
        pagina.click("#btn-deshacer")
        expect(pagina.locator(".punto:not(.seleccion-preview)")).to_have_count(14)
        expect(pagina.locator("#btn-deshacer")).to_be_disabled()
        estado = _estado(contexto, base)
        assert all(p["id"] != "P15" for p in estado["proyecto"]["points"])
        assert estado["puede_deshacer"] is False

        # Exportación completa, archivos servidos y vista del unifilar.
        pagina.click("#btn-exportar")
        expect(pagina.locator("#archivos a").first).to_be_visible(timeout=20000)
        expect(pagina.locator("#estado-linea")).to_contain_text("Archivos exportados")
        enlaces = pagina.locator("#archivos a").evaluate_all(
            "elementos => elementos.map(e => e.getAttribute('href'))"
        )
        etiquetas = pagina.locator("#archivos a").evaluate_all(
            "elementos => elementos.map(e => e.textContent.trim())"
        )
        assert len(enlaces) >= 3
        assert {"Unifilar SVG", "Cuadro CSV", "Materiales CSV"} <= set(etiquetas)
        for enlace in enlaces:
            respuesta = contexto.request.get(base + enlace)
            assert respuesta.status == 200
            assert len(respuesta.body()) > 0
            assert (salida / Path(enlace).name).is_file()
        expect(pagina.locator("#unifilar")).to_be_visible()
        assert pagina.locator("#unifilar").evaluate(
            "imagen => imagen.complete && imagen.src.includes('unifilar.svg')"
        )

        _captura(pagina, artefactos / "editor-desktop.png")

        # Guardar descarga el JSON actual.
        with pagina.expect_download() as descarga_info:
            pagina.click("a[href='/api/proyecto']")
        descarga = descarga_info.value
        assert descarga.suggested_filename == "proyecto.json"
        descargado = json.loads(Path(descarga.path()).read_text(encoding="utf-8"))
        assert descargado["project"]["name"].startswith("Casa simple")
        descarga.save_as(artefactos / "proyecto-descargado.json")

        # Abrir recarga un proyecto validado y reinicia el deshacer.
        descargado["project"]["name"] = "Casa recargada E2E"
        ruta_proyecto = artefactos / "proyecto-recargado.json"
        ruta_proyecto.write_text(
            json.dumps(descargado, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        pagina.set_input_files("#archivo-proyecto", str(ruta_proyecto))
        expect(pagina.locator("#proyecto-nombre")).to_contain_text("Casa recargada E2E")
        expect(pagina.locator("#estado-linea")).to_contain_text("cargado")
        assert _estado(contexto, base)["proyecto"]["project"]["name"] == "Casa recargada E2E"
        expect(pagina.locator("#btn-deshacer")).to_be_disabled()

        # Sin clave, el chat explica el 503 y el resto sigue funcionando.
        pagina.fill("#chat-texto", "Agrega un dormitorio")
        pagina.click("#btn-enviar")
        expect(pagina.locator("#chat-aviso")).to_contain_text("CADBIM_LLM_KEY")
        expect(pagina.locator("#mensajes")).to_contain_text("Chat no configurado")

        _sin_errores_de_navegador(errores_pagina, errores_consola)
        navegador.close()


def test_vista_movil_y_colocacion(servidor):
    base, _ = servidor
    artefactos = _artefactos()
    errores_pagina: list[str] = []

    with sync_playwright() as playwright:
        navegador = _lanzar_navegador(playwright)
        contexto = navegador.new_context(
            viewport={"width": 390, "height": 844},
            is_mobile=True,
            has_touch=True,
            device_scale_factor=3,
        )
        pagina = contexto.new_page()
        pagina.set_default_timeout(15000)
        pagina.on("pageerror", lambda error: errores_pagina.append(str(error)))

        pagina.goto(base, wait_until="networkidle")
        expect(pagina.locator("#proyecto-nombre")).to_contain_text("Casa simple")
        expect(pagina.locator("polygon.ambiente")).to_have_count(3)

        caja = pagina.locator("#plano").bounding_box()
        assert caja is not None
        assert caja["width"] > 300
        assert caja["height"] > 150
        assert pagina.evaluate("document.documentElement.scrollWidth") <= pagina.evaluate(
            "window.innerWidth + 1"
        )

        ambiente = pagina.locator("polygon.ambiente").first.bounding_box()
        assert ambiente is not None
        pagina.mouse.click(
            ambiente["x"] + ambiente["width"] / 2,
            ambiente["y"] + ambiente["height"] / 2,
        )
        expect(pagina.locator("#btn-punto")).to_be_enabled()
        expect(pagina.locator("#pista-punto")).to_contain_text("dentro de Sala")
        pagina.click("#btn-punto")
        expect(pagina.locator(".punto:not(.seleccion-preview)")).to_have_count(15)
        expect(pagina.locator("#veredicto")).to_contain_text("Conforme")

        _captura(pagina, artefactos / "editor-movil.png")
        assert errores_pagina == []
        navegador.close()
