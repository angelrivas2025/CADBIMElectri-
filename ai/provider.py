"""Proveedores de chat compatibles con la API de OpenAI.

La clave se lee del entorno (``CADBIM_LLM_KEY``); nunca se guarda en el proyecto.
"""
from __future__ import annotations

import json
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from typing import Any


class ErrorProveedor(Exception):
    """El proveedor no respondió o devolvió una estructura inesperada."""


@dataclass
class LlamadaHerramienta:
    id: str
    nombre: str
    arguments: dict[str, Any]


@dataclass
class Respuesta:
    texto: str
    llamadas: list[LlamadaHerramienta] = field(default_factory=list)
    mensaje: dict[str, Any] = field(default_factory=dict)


def parsear_mensaje(message: dict[str, Any]) -> Respuesta:
    llamadas: list[LlamadaHerramienta] = []
    for indice, crudo in enumerate(message.get("tool_calls") or []):
        funcion = crudo.get("function") or {}
        nombre = funcion.get("name")
        if not nombre:
            raise ErrorProveedor("tool_call sin nombre de función")
        argumentos = funcion.get("arguments") or "{}"
        try:
            arguments = (
                json.loads(argumentos) if isinstance(argumentos, str) else argumentos
            )
        except json.JSONDecodeError as exc:
            raise ErrorProveedor(
                f"argumentos de '{nombre}' no son JSON válido: {exc}"
            ) from exc
        if not isinstance(arguments, dict):
            raise ErrorProveedor(
                f"argumentos de '{nombre}' deben ser un objeto JSON"
            )
        llamadas.append(
            LlamadaHerramienta(
                id=crudo.get("id") or f"call_{indice}",
                nombre=nombre,
                arguments=arguments,
            )
        )
    return Respuesta(
        texto=message.get("content") or "",
        llamadas=llamadas,
        mensaje=message,
    )


class ProveedorOpenAI:
    """Cliente mínimo de ``/chat/completions`` con soporte de tool calls."""

    def __init__(
        self,
        api_key: str,
        *,
        base_url: str = "https://api.openai.com/v1",
        model: str = "gpt-4o-mini",
        timeout: float = 60.0,
    ):
        if not api_key:
            raise ErrorProveedor("falta la clave del proveedor")
        self.url = base_url.rstrip("/") + "/chat/completions"
        self.api_key = api_key
        self.model = model
        self.timeout = timeout

    def responder(
        self, messages: list[dict[str, Any]], tools: list[dict[str, Any]]
    ) -> Respuesta:
        payload = {
            "model": self.model,
            "messages": messages,
            "tools": [
                {
                    "type": "function",
                    "function": {
                        "name": herramienta["name"],
                        "description": herramienta["description"],
                        "parameters": herramienta["parameters"],
                    },
                }
                for herramienta in tools
            ],
        }
        peticion = urllib.request.Request(
            self.url,
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.api_key}",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(peticion, timeout=self.timeout) as respuesta:
                datos = json.load(respuesta)
        except urllib.error.HTTPError as exc:
            detalle = exc.read().decode("utf-8", errors="replace")[:300]
            raise ErrorProveedor(f"HTTP {exc.code}: {detalle}") from exc
        except (urllib.error.URLError, TimeoutError) as exc:
            raise ErrorProveedor(f"no se pudo contactar al proveedor: {exc}") from exc

        try:
            mensaje = datos["choices"][0]["message"]
        except (KeyError, IndexError, TypeError) as exc:
            raise ErrorProveedor("respuesta sin 'choices[0].message'") from exc
        return parsear_mensaje(mensaje)
