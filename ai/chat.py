"""Bucle de conversación: el modelo propone llamadas y el agente las aplica."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Protocol

from ai.agent import Agente
from ai.provider import ErrorProveedor, Respuesta
from ai.tools import ErrorHerramienta, describir

SISTEMA_PATH = Path(__file__).with_name("prompts") / "sistema.md"


class ErrorChat(Exception):
    """La conversación no pudo completarse."""


class Proveedor(Protocol):
    def responder(
        self, messages: list[dict[str, Any]], tools: list[dict[str, Any]]
    ) -> Respuesta: ...


class Chat:
    def __init__(
        self,
        agente: Agente,
        proveedor: Proveedor,
        *,
        max_turnos: int = 8,
        sistema: str | None = None,
    ):
        if max_turnos < 1:
            raise ValueError("max_turnos debe ser al menos 1")
        self.agente = agente
        self.proveedor = proveedor
        self.max_turnos = max_turnos
        self.mensajes: list[dict[str, Any]] = [
            {
                "role": "system",
                "content": sistema or SISTEMA_PATH.read_text(encoding="utf-8"),
            }
        ]

    def enviar(self, texto: str) -> str:
        self.mensajes.append({"role": "user", "content": texto})
        for _ in range(self.max_turnos):
            respuesta = self.proveedor.responder(self.mensajes, describir())
            mensaje = respuesta.mensaje or self._mensaje(respuesta)
            self.mensajes.append(mensaje)
            if not respuesta.llamadas:
                return respuesta.texto
            for llamada in respuesta.llamadas:
                try:
                    resultado = self.agente.aplicar(llamada.nombre, llamada.arguments)
                except ErrorHerramienta as exc:
                    resultado = {"error": str(exc)}
                self.mensajes.append(
                    {
                        "role": "tool",
                        "tool_call_id": llamada.id,
                        "content": json.dumps(resultado, ensure_ascii=False),
                    }
                )
        raise ErrorChat(
            f"el modelo no terminó en {self.max_turnos} turno(s) de herramientas"
        )

    @staticmethod
    def _mensaje(respuesta: Respuesta) -> dict[str, Any]:
        mensaje: dict[str, Any] = {
            "role": "assistant",
            "content": respuesta.texto,
        }
        if respuesta.llamadas:
            mensaje["tool_calls"] = [
                {
                    "id": llamada.id,
                    "type": "function",
                    "function": {
                        "name": llamada.nombre,
                        "arguments": json.dumps(llamada.arguments, ensure_ascii=False),
                    },
                }
                for llamada in respuesta.llamadas
            ]
        return mensaje


__all__ = ["Chat", "ErrorChat", "ErrorProveedor", "Proveedor"]
