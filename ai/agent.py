"""Sesión de edición asistida: la IA propone, el motor valida.

Cada llamada se aplica sobre una copia de seguridad; si la herramienta falla o
el proyecto deja de cumplir esquema o referencias, se revierte por completo.
"""
from __future__ import annotations

import copy
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ai.tools import ErrorHerramienta, ejecutar
from core.model.loader import reference_issues, schema_issues

SOLO_LECTURA = {"get_project_summary", "run_validation", "export"}


class Agente:
    """Proyecto en memoria con historial de llamadas y deshacer."""

    def __init__(self, project: dict[str, Any]):
        self.proyecto = copy.deepcopy(project)
        self.historial: list[dict[str, Any]] = []
        self._copias: list[dict[str, Any]] = []

    @classmethod
    def desde_archivo(cls, ruta: str | Path) -> "Agente":
        from core.model.loader import load_project

        return cls(load_project(ruta))

    @property
    def puede_deshacer(self) -> bool:
        return bool(self._copias)

    def cargar(self, project: dict[str, Any]) -> None:
        self.proyecto = copy.deepcopy(project)
        self.historial.clear()
        self._copias.clear()

    def aplicar(self, herramienta: str, arguments: dict[str, Any]) -> Any:
        antes = copy.deepcopy(self.proyecto)
        try:
            resultado = ejecutar(self.proyecto, herramienta, arguments)
        except Exception:
            self.proyecto = antes
            raise

        problemas = schema_issues(self.proyecto)
        if not problemas:
            problemas = reference_issues(self.proyecto)
        if problemas:
            self.proyecto = antes
            raise ErrorHerramienta(
                f"'{herramienta}' dejaría el proyecto inválido: " + "; ".join(problemas)
            )

        if herramienta in SOLO_LECTURA:
            return resultado

        self.proyecto.setdefault("history", []).append(
            {
                "timestamp": datetime.now(timezone.utc).strftime(
                    "%Y-%m-%dT%H:%M:%SZ"
                ),
                "author": "ia",
                "action": f"{herramienta} "
                + json.dumps(arguments, ensure_ascii=False, sort_keys=True),
            }
        )

        self._copias.append(antes)
        self.historial.append(
            {
                "tool": herramienta,
                "arguments": copy.deepcopy(arguments),
                "result": resultado,
            }
        )
        return resultado

    def aplicar_plan(self, llamadas: list[dict[str, Any]]) -> list[Any]:
        inicio = copy.deepcopy(self.proyecto)
        historial_inicio = len(self.historial)
        copias_inicio = len(self._copias)
        resultados = []
        try:
            for numero, llamada in enumerate(llamadas, start=1):
                if not isinstance(llamada, dict) or "tool" not in llamada:
                    raise ErrorHerramienta(
                        f"llamada {numero}: se esperaba "
                        "{'tool': ..., 'arguments': ...}"
                    )
                arguments = llamada.get("arguments") or {}
                if not isinstance(arguments, dict):
                    raise ErrorHerramienta(
                        f"llamada {numero}: 'arguments' debe ser un objeto"
                    )
                try:
                    resultados.append(self.aplicar(llamada["tool"], arguments))
                except ErrorHerramienta as exc:
                    raise ErrorHerramienta(f"llamada {numero}: {exc}") from exc
        except Exception:
            self.proyecto = inicio
            del self.historial[historial_inicio:]
            del self._copias[copias_inicio:]
            raise
        return resultados

    def deshacer(self, n: int = 1) -> dict[str, Any]:
        if n < 1:
            raise ValueError("n debe ser al menos 1")
        if n > len(self._copias):
            raise ErrorHerramienta(
                f"no hay {n} cambio(s) para deshacer (historial: {len(self._copias)})"
            )
        for _ in range(n):
            self.proyecto = self._copias.pop()
            self.historial.pop()
        return self.proyecto

    def guardar(self, ruta: str | Path) -> Path:
        import json

        destino = Path(ruta)
        destino.parent.mkdir(parents=True, exist_ok=True)
        destino.write_text(
            json.dumps(self.proyecto, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        return destino
