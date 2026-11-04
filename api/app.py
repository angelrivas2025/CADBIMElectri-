"""API local del editor: proyecto, herramientas, validación, export y chat."""
from __future__ import annotations

import json
import os
import threading
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Response
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from ai.agent import Agente
from ai.chat import Chat, ErrorChat
from ai.project import proyecto_nuevo
from ai.provider import ErrorProveedor, ProveedorOpenAI
from ai.tools import ErrorHerramienta, describir, ejecutar
from core.calc.validate import validar_proyecto
from core.model.loader import (
    reference_issues,
    schema_issues,
)

WEB = Path(__file__).with_name("web")


class LlamadaEntrada(BaseModel):
    tool: str = Field(min_length=1)
    arguments: dict[str, Any] = Field(default_factory=dict)


class MensajeEntrada(BaseModel):
    mensaje: str = Field(min_length=1)


class DeshacerEntrada(BaseModel):
    n: int = Field(default=1, ge=1)


class ProyectoEntrada(BaseModel):
    proyecto: dict[str, Any]


class _AgenteApi(Agente):
    """Agente de la API: limita las exportaciones a la carpeta servida."""

    def __init__(self, project: dict[str, Any], raiz: Path):
        super().__init__(project)
        self._raiz = raiz.resolve()

    def aplicar(self, herramienta: str, arguments: dict[str, Any]) -> Any:
        if (
            herramienta == "export"
            and isinstance(arguments, dict)
            and isinstance(arguments.get("path"), str)
        ):
            destino = Path(arguments["path"]).resolve()
            if destino != self._raiz and self._raiz not in destino.parents:
                raise ErrorHerramienta(
                    "la API solo exporta dentro de la carpeta de salida"
                )
        return super().aplicar(herramienta, arguments)


def _validacion(project: dict[str, Any]) -> dict[str, Any]:
    informe = validar_proyecto(project)
    circuitos = []
    for c in ((informe.get("dimensionamiento") or {}).get("circuits") or []):
        circuitos.append(
            {
                "id": c["id"],
                "breaker_a": c.get("breaker_a"),
                "section_mm2": c.get("section_mm2"),
                "current_a": c.get("current_a"),
                "voltage_drop_pct": c.get("voltage_drop_pct"),
            }
        )
    return {
        "conforme": informe["ok"],
        "errores": informe["errores"],
        "avisos": informe["avisos"],
        "circuitos": circuitos,
        "alimentador": informe.get("alimentador"),
    }


def _crear_proveedor() -> ProveedorOpenAI | None:
    clave = os.environ.get("CADBIM_LLM_KEY")
    if not clave:
        return None
    return ProveedorOpenAI(
        clave,
        base_url=os.environ.get("CADBIM_LLM_URL", "https://api.openai.com/v1"),
        model=os.environ.get("CADBIM_LLM_MODEL", "gpt-4o-mini"),
    )


def create_app(
    proyecto: dict[str, Any] | None = None,
    *,
    salida: str | Path = "salida/web",
    proveedor: Any | None = None,
) -> FastAPI:
    destino = Path(salida).resolve()
    agente = _AgenteApi(
        proyecto if proyecto is not None else proyecto_nuevo("Proyecto nuevo"),
        destino,
    )
    proveedor_chat = proveedor if proveedor is not None else _crear_proveedor()
    chat = Chat(agente, proveedor_chat) if proveedor_chat is not None else None
    candado = threading.Lock()
    destino.mkdir(parents=True, exist_ok=True)

    app = FastAPI(title="CADBIMElectri", version="0.1.0")

    def estado() -> dict[str, Any]:
        return {
            "proyecto": agente.proyecto,
            "resumen": ejecutar(agente.proyecto, "get_project_summary", {}),
            "validacion": _validacion(agente.proyecto),
            "puede_deshacer": agente.puede_deshacer,
        }

    @app.get("/api/estado")
    def obtener_estado() -> dict[str, Any]:
        with candado:
            return estado()

    @app.get("/api/proyecto")
    def descargar_proyecto() -> Response:
        with candado:
            contenido = (
                json.dumps(agente.proyecto, ensure_ascii=False, indent=2) + "\n"
            )
        return Response(
            content=contenido,
            media_type="application/json",
            headers={
                "Content-Disposition": 'attachment; filename="proyecto.json"'
            },
        )

    @app.post("/api/proyecto")
    def abrir_proyecto(entrada: ProyectoEntrada) -> dict[str, Any]:
        problemas = schema_issues(entrada.proyecto)
        if not problemas:
            problemas = reference_issues(entrada.proyecto)
        if problemas:
            raise HTTPException(status_code=422, detail="; ".join(problemas))
        with candado:
            agente.cargar(entrada.proyecto)
            return estado()

    @app.get("/api/herramientas")
    def listar_herramientas() -> list[dict[str, Any]]:
        return describir()

    @app.post("/api/herramienta")
    def aplicar_herramienta(entrada: LlamadaEntrada) -> dict[str, Any]:
        with candado:
            try:
                resultado = agente.aplicar(entrada.tool, entrada.arguments)
            except ErrorHerramienta as exc:
                raise HTTPException(status_code=422, detail=str(exc)) from exc
            return {"resultado": resultado, **estado()}

    @app.post("/api/deshacer")
    def deshacer(entrada: DeshacerEntrada) -> dict[str, Any]:
        with candado:
            try:
                agente.deshacer(entrada.n)
            except (ErrorHerramienta, ValueError) as exc:
                raise HTTPException(status_code=422, detail=str(exc)) from exc
            return estado()

    @app.post("/api/validar")
    def validar() -> dict[str, Any]:
        with candado:
            return _validacion(agente.proyecto)

    def _estado_sin_bloqueo() -> dict[str, Any]:
        return {
            "proyecto": agente.proyecto,
            "validacion": _validacion(agente.proyecto),
            "puede_deshacer": agente.puede_deshacer,
        }

    @app.post("/api/chat")
    def conversar(entrada: MensajeEntrada) -> dict[str, Any]:
        if chat is None:
            raise HTTPException(
                status_code=503,
                detail="Chat no configurado: exporte CADBIM_LLM_KEY en el servidor.",
            )
        with candado:
            try:
                respuesta = chat.enviar(entrada.mensaje)
            except (ErrorProveedor, ErrorChat) as exc:
                raise HTTPException(status_code=502, detail=str(exc)) from exc
            return {"respuesta": respuesta, **_estado_sin_bloqueo()}

    @app.post("/api/exportar")
    def exportar() -> dict[str, Any]:
        try:
            from exporters.export import exportar_todo
        except ImportError as exc:
            raise HTTPException(
                status_code=503,
                detail=(
                    "Exportación no disponible: instale el extra "
                    f"'cadbimelectri[export]' ({exc})"
                ),
            ) from exc

        with candado:
            informe = validar_proyecto(agente.proyecto)
            rutas = exportar_todo(agente.proyecto, informe, destino)
        return {
            "archivos": {
                clave: f"/salida/{ruta.name}" for clave, ruta in rutas.items()
            },
            "errores": informe["errores"],
        }

    app.mount("/estatico", StaticFiles(directory=WEB), name="estatico")
    app.mount("/salida", StaticFiles(directory=destino), name="salida")

    @app.get("/")
    def indice() -> FileResponse:
        return FileResponse(WEB / "index.html")

    return app
