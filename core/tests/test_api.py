import copy
import json
from pathlib import Path

from fastapi.testclient import TestClient

from ai.provider import LlamadaHerramienta, Respuesta
from api.app import create_app
from core.model.loader import load_project

CONFORME = Path(__file__).resolve().parents[2] / "examples" / "casa-conforme.json"


def _respuesta(texto="", llamadas=None):
    llamadas = llamadas or []
    mensaje = {"role": "assistant", "content": texto}
    if llamadas:
        mensaje["tool_calls"] = [
            {
                "id": llamada.id,
                "type": "function",
                "function": {
                    "name": llamada.nombre,
                    "arguments": json.dumps(llamada.arguments),
                },
            }
            for llamada in llamadas
        ]
    return Respuesta(texto=texto, llamadas=llamadas, mensaje=mensaje)


class ProveedorFalso:
    def __init__(self, respuestas):
        self.respuestas = list(respuestas)
        self.vistas = []

    def responder(self, messages, tools):
        self.vistas.append(copy.deepcopy(messages))
        return self.respuestas.pop(0)


def _cliente(tmp_path, **kwargs):
    app = create_app(
        load_project(CONFORME), salida=tmp_path / "salida", **kwargs
    )
    return TestClient(app)


def test_estado_inicial(tmp_path):
    cliente = _cliente(tmp_path)
    respuesta = cliente.get("/api/estado")
    assert respuesta.status_code == 200
    datos = respuesta.json()
    assert datos["proyecto"]["project"]["name"].startswith("Casa simple")
    assert datos["resumen"]["ambientes"] == 3
    assert datos["resumen"]["circuitos"] == ["C1", "C2", "C3"]
    assert datos["validacion"]["conforme"] is True
    assert [c["id"] for c in datos["validacion"]["circuitos"]] == ["C1", "C2", "C3"]
    assert datos["validacion"]["alimentador"]["section_mm2"]
    assert datos["puede_deshacer"] is False


def test_app_sin_proyecto_arranca_vacio(tmp_path, monkeypatch):
    monkeypatch.delenv("CADBIM_LLM_KEY", raising=False)
    cliente = TestClient(create_app(salida=tmp_path / "salida"))
    datos = cliente.get("/api/estado").json()
    assert datos["proyecto"]["project"]["name"] == "Proyecto nuevo"
    assert datos["resumen"]["ambientes"] == 0
    assert datos["puede_deshacer"] is False


def test_herramientas_expone_el_catalogo(tmp_path):
    cliente = _cliente(tmp_path)
    respuesta = cliente.get("/api/herramientas")
    assert respuesta.status_code == 200
    nombres = {herramienta["name"] for herramienta in respuesta.json()}
    assert {"add_room", "place_point", "run_validation", "export"} <= nombres
    assert all("parameters" in h for h in respuesta.json())


def test_herramienta_y_deshacer(tmp_path):
    cliente = _cliente(tmp_path)
    original = cliente.get("/api/estado").json()["proyecto"]["rooms"][0]["name"]

    respuesta = cliente.post(
        "/api/herramienta",
        json={"tool": "update_room", "arguments": {"id": "R1", "name": "Living"}},
    )
    assert respuesta.status_code == 200
    datos = respuesta.json()
    assert datos["proyecto"]["rooms"][0]["name"] == "Living"
    assert datos["proyecto"]["history"][-1]["author"] == "ia"
    assert datos["puede_deshacer"] is True
    assert datos["resultado"] == {"id": "R1"}

    respuesta = cliente.post("/api/deshacer", json={"n": 1})
    assert respuesta.status_code == 200
    datos = respuesta.json()
    assert datos["proyecto"]["rooms"][0]["name"] == original
    assert datos["puede_deshacer"] is False

    assert cliente.post("/api/deshacer", json={"n": 1}).status_code == 422


def test_herramienta_invalida_no_cambia_el_proyecto(tmp_path):
    cliente = _cliente(tmp_path)
    antes = cliente.get("/api/estado").json()["proyecto"]

    respuesta = cliente.post(
        "/api/herramienta",
        json={
            "tool": "place_point",
            "arguments": {
                "id": "P99", "type": "tug", "room": "R1", "position": [1, 1],
            },
        },
    )
    assert respuesta.status_code == 422
    assert "power" in respuesta.json()["detail"].lower()

    respuesta = cliente.post(
        "/api/herramienta", json={"tool": "no_existe", "arguments": {}}
    )
    assert respuesta.status_code == 422

    assert cliente.get("/api/estado").json()["proyecto"] == antes


def test_punto_desde_el_editor(tmp_path):
    cliente = _cliente(tmp_path)
    respuesta = cliente.post(
        "/api/herramienta",
        json={
            "tool": "place_point",
            "arguments": {
                "id": "P99",
                "type": "tug",
                "room": "R1",
                "position": [1.25, 1.5],
                "power": 100,
                "height": 1.1,
            },
        },
    )
    assert respuesta.status_code == 200
    datos = respuesta.json()
    punto = next(p for p in datos["proyecto"]["points"] if p["id"] == "P99")
    assert punto["position"] == [1.25, 1.5]
    assert punto["power"] == 100
    assert datos["validacion"]["conforme"] is True

    validacion = cliente.post("/api/validar").json()
    assert validacion["conforme"] is True
    assert "avisos" in validacion


def test_descargar_y_abrir_proyecto(tmp_path):
    cliente = _cliente(tmp_path)
    descarga = cliente.get("/api/proyecto")
    assert descarga.status_code == 200
    assert "attachment" in descarga.headers["content-disposition"]
    proyecto = descarga.json()
    assert proyecto["project"]["name"].startswith("Casa simple")

    cliente.post(
        "/api/herramienta",
        json={"tool": "update_room", "arguments": {"id": "R1", "name": "Estar"}},
    )
    proyecto["project"]["name"] = "Casa cargada"
    respuesta = cliente.post("/api/proyecto", json={"proyecto": proyecto})
    assert respuesta.status_code == 200
    datos = respuesta.json()
    assert datos["proyecto"]["project"]["name"] == "Casa cargada"
    assert datos["puede_deshacer"] is False

    invalido = copy.deepcopy(proyecto)
    invalido["points"][0]["room"] = "R99"
    respuesta = cliente.post("/api/proyecto", json={"proyecto": invalido})
    assert respuesta.status_code == 422
    assert "R99" in respuesta.json()["detail"]
    assert (
        cliente.get("/api/estado").json()["proyecto"]["project"]["name"]
        == "Casa cargada"
    )


def test_exportacion_de_la_api_queda_en_su_carpeta(tmp_path):
    cliente = _cliente(tmp_path)
    fuera = tmp_path / "fuera" / "unifilar.svg"
    respuesta = cliente.post(
        "/api/herramienta",
        json={
            "tool": "export",
            "arguments": {"format": "svg", "path": str(fuera)},
        },
    )
    assert respuesta.status_code == 422
    assert "carpeta de salida" in respuesta.json()["detail"]
    assert not fuera.exists()

    dentro = tmp_path / "salida" / "unifilar.svg"
    respuesta = cliente.post(
        "/api/herramienta",
        json={
            "tool": "export",
            "arguments": {"format": "svg", "path": str(dentro)},
        },
    )
    assert respuesta.status_code == 200
    assert dentro.is_file()


def test_exportar_y_servir_archivos(tmp_path):
    cliente = _cliente(tmp_path)
    respuesta = cliente.post("/api/exportar")
    assert respuesta.status_code == 200
    datos = respuesta.json()
    assert datos["errores"] == []
    assert {"svg", "csv", "materiales"} <= set(datos["archivos"])

    for clave in ("svg", "csv", "materiales"):
        assert datos["archivos"][clave].startswith("/salida/")
        assert (tmp_path / "salida" / Path(datos["archivos"][clave]).name).is_file()
        assert cliente.get(datos["archivos"][clave]).status_code == 200


def test_raiz_y_estaticos(tmp_path):
    cliente = _cliente(tmp_path)
    indice = cliente.get("/")
    assert indice.status_code == 200
    assert "CADBIMElectri" in indice.text
    assert cliente.get("/estatico/styles.css").status_code == 200
    assert cliente.get("/estatico/app.js").status_code == 200


def test_chat_sin_clave(tmp_path, monkeypatch):
    monkeypatch.delenv("CADBIM_LLM_KEY", raising=False)
    cliente = _cliente(tmp_path)
    respuesta = cliente.post("/api/chat", json={"mensaje": "hola"})
    assert respuesta.status_code == 503
    assert "CADBIM_LLM_KEY" in respuesta.json()["detail"]


def test_chat_aplica_herramientas(tmp_path):
    proveedor = ProveedorFalso(
        [
            _respuesta(
                llamadas=[
                    LlamadaHerramienta(
                        "1", "update_room", {"id": "R1", "name": "Living"}
                    )
                ]
            ),
            _respuesta("Sala renombrada."),
        ]
    )
    cliente = _cliente(tmp_path, proveedor=proveedor)
    respuesta = cliente.post("/api/chat", json={"mensaje": "Renombra la sala"})
    assert respuesta.status_code == 200
    datos = respuesta.json()
    assert datos["respuesta"] == "Sala renombrada."
    assert datos["proyecto"]["rooms"][0]["name"] == "Living"
    assert datos["puede_deshacer"] is True
    assert proveedor.vistas[0][0]["role"] == "system"


def test_cuerpos_invalidos_son_rechazados(tmp_path):
    cliente = _cliente(tmp_path)
    assert cliente.post("/api/chat", json={"mensaje": ""}).status_code == 422
    assert cliente.post("/api/herramienta", json={"arguments": {}}).status_code == 422
    assert cliente.post("/api/deshacer", json={"n": 0}).status_code == 422


def test_cli_api_arranca_uvicorn(tmp_path, monkeypatch):
    import uvicorn

    from api.__main__ import main

    capturado = {}

    def falso_run(app, host, port):
        capturado.update(host=host, port=port, app=app)

    monkeypatch.setattr(uvicorn, "run", falso_run)
    codigo = main(
        [
            "--proyecto",
            str(CONFORME),
            "--host",
            "127.0.0.1",
            "--port",
            "8123",
            "--salida",
            str(tmp_path / "salida"),
        ]
    )
    assert codigo == 0
    assert capturado["port"] == 8123
    assert capturado["app"].title == "CADBIMElectri"


def test_cli_api_rechaza_archivo_inexistente(tmp_path):
    from api.__main__ import main

    assert main(["--proyecto", str(tmp_path / "nada.json")]) == 2
