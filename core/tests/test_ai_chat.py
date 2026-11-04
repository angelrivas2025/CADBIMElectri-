import copy
import json
from pathlib import Path

import pytest

from ai import Agente
from ai.__main__ import main
from ai.chat import Chat, ErrorChat
from ai.provider import (
    ErrorProveedor,
    LlamadaHerramienta,
    ProveedorOpenAI,
    Respuesta,
    parsear_mensaje,
)
from ai.tools import describir
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


def _agente():
    return Agente(load_project(CONFORME))


def test_chat_aplica_herramienta_y_responde():
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
    agente = _agente()
    chat = Chat(agente, proveedor)
    assert chat.enviar("Renombra la sala") == "Sala renombrada."
    assert agente.proyecto["rooms"][0]["name"] == "Living"
    assert agente.proyecto["history"][-1]["action"].startswith("update_room ")
    roles = [m["role"] for m in chat.mensajes]
    assert roles == ["system", "user", "assistant", "tool", "assistant"]
    assert chat.mensajes[0]["content"]
    assert "R1" in chat.mensajes[3]["content"]
    assert any(h["name"] == "add_room" for h in describir())


def test_chat_devuelve_error_al_modelo():
    proveedor = ProveedorFalso(
        [
            _respuesta(
                llamadas=[
                    LlamadaHerramienta(
                        "1",
                        "add_room",
                        {
                            "id": "R1", "name": "Otra", "type": "sala",
                            "polygon": [[0, 0], [1, 0], [1, 1]],
                        },
                    )
                ]
            ),
            _respuesta("No pude agregarla."),
        ]
    )
    agente = _agente()
    antes = copy.deepcopy(agente.proyecto)
    chat = Chat(agente, proveedor)
    assert chat.enviar("Agrega otra sala") == "No pude agregarla."
    resultado = json.loads(chat.mensajes[3]["content"])
    assert "duplicado" in resultado["error"]
    assert agente.proyecto == antes


def test_chat_limita_los_turnos():
    llamada = LlamadaHerramienta("1", "get_project_summary", {})
    proveedor = ProveedorFalso([_respuesta(llamadas=[llamada]) for _ in range(2)])
    chat = Chat(_agente(), proveedor, max_turnos=2)
    with pytest.raises(ErrorChat, match="no terminó en 2"):
        chat.enviar("hola")


def test_parsear_mensaje_y_errores():
    respuesta = parsear_mensaje(
        {
            "role": "assistant",
            "content": "",
            "tool_calls": [
                {
                    "id": "abc",
                    "type": "function",
                    "function": {
                        "name": "add_room",
                        "arguments": '{"id": "R9", "name": "X", "type": "sala", '
                        '"polygon": [[0, 0], [1, 0], [1, 1]]}',
                    },
                }
            ],
        }
    )
    assert respuesta.llamadas[0].nombre == "add_room"
    assert respuesta.llamadas[0].arguments["id"] == "R9"

    with pytest.raises(ErrorProveedor, match="JSON válido"):
        parsear_mensaje(
            {
                "tool_calls": [
                    {"function": {"name": "add_room", "arguments": "{malo"}},
                ]
            }
        )
    with pytest.raises(ErrorProveedor, match="objeto JSON"):
        parsear_mensaje(
            {
                "tool_calls": [
                    {"function": {"name": "add_room", "arguments": "[1, 2]"}},
                ]
            }
        )


def test_proveedor_openai_arma_la_peticion(monkeypatch):
    capturado = {}

    class RespuestaHTTP:
        def __init__(self, datos):
            self._datos = json.dumps(datos).encode("utf-8")

        def read(self):
            return self._datos

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

    def falso_urlopen(peticion, timeout):
        capturado["peticion"] = peticion
        capturado["timeout"] = timeout
        return RespuestaHTTP(
            {"choices": [{"message": {"role": "assistant", "content": "ok"}}]}
        )

    monkeypatch.setattr("urllib.request.urlopen", falso_urlopen)
    proveedor = ProveedorOpenAI(
        "clave", base_url="https://example.test/v1", model="modelo"
    )
    respuesta = proveedor.responder([{"role": "user", "content": "hola"}], describir())
    assert respuesta.texto == "ok"
    peticion = capturado["peticion"]
    assert peticion.full_url == "https://example.test/v1/chat/completions"
    assert peticion.get_header("Authorization") == "Bearer clave"
    datos = json.loads(peticion.data)
    assert datos["model"] == "modelo"
    assert datos["messages"][0]["content"] == "hola"
    assert {t["function"]["name"] for t in datos["tools"]} == {
        h["name"] for h in describir()
    }


def test_cli_chat_sin_clave(monkeypatch, capsys):
    monkeypatch.delenv("CADBIM_LLM_KEY", raising=False)
    assert main(["chat", "--nuevo", "Casa", "--mensaje", "hola"]) == 2
    assert "CADBIM_LLM_KEY" in capsys.readouterr().out
