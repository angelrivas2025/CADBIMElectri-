"""CLI del asistente: catálogo, planes de herramientas y chat.

Un plan es una lista de llamadas emitidas por el modelo:
``[{"tool": "add_room", "arguments": {...}}, ...]``.
El motor valida cada llamada y el proyecto resultante antes de guardar.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from ai.agent import Agente
from ai.chat import Chat, ErrorChat
from ai.project import proyecto_nuevo
from ai.provider import ErrorProveedor, ProveedorOpenAI
from ai.tools import ErrorHerramienta, describir
from core.calc.validate import validar_proyecto
from core.model.loader import ProjectError


def _cargar_plan(ruta: Path) -> list[dict]:
    datos = json.loads(ruta.read_text(encoding="utf-8"))
    if isinstance(datos, dict):
        datos = datos.get("calls")
    if not isinstance(datos, list):
        raise ValueError("el plan debe ser una lista de llamadas o {'calls': [...]}")
    return datos


def _imprimir_validacion(project: dict) -> bool:
    informe = validar_proyecto(project)
    for error in informe["errores"]:
        print(f"ERROR: {error}")
    for aviso in informe["avisos"]:
        print(f"AVISO: {aviso}")
    if informe["ok"]:
        print("Proyecto sin errores de cumplimiento.")
    return informe["ok"]


def _abrir_agente(
    args: argparse.Namespace, parser: argparse.ArgumentParser
) -> Agente | None:
    try:
        if args.proyecto is not None:
            return Agente.desde_archivo(args.proyecto)
        if args.nuevo:
            return Agente(proyecto_nuevo(args.nuevo))
    except (ProjectError, OSError) as exc:
        print(f"Error al cargar el proyecto: {exc}")
        return None
    parser.error("indique --proyecto o --nuevo")
    return None


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m ai",
        description="Herramientas del asistente CADBIMElectri y aplicación de planes.",
    )
    sub = parser.add_subparsers(dest="comando", required=True)

    catalogo = sub.add_parser("herramientas", help="Lista las herramientas disponibles")
    catalogo.add_argument("--json", action="store_true", help="Salida JSON")

    aplicar = sub.add_parser("aplicar", help="Aplica un plan de llamadas")
    aplicar.add_argument("plan", type=Path, help="JSON con la lista de llamadas")
    origen = aplicar.add_mutually_exclusive_group()
    origen.add_argument("--proyecto", type=Path, help="Proyecto de entrada")
    origen.add_argument("--nuevo", metavar="NOMBRE", help="Crea un proyecto vacío")
    aplicar.add_argument("--salida", type=Path, help="Ruta del proyecto resultante")
    aplicar.add_argument(
        "--dry-run", action="store_true", help="No escribe el proyecto resultante"
    )

    validar = sub.add_parser("validar", help="Valida un proyecto con el motor")
    validar.add_argument("proyecto", type=Path)

    chat = sub.add_parser("chat", help="Conversa con un proveedor compatible OpenAI")
    origen_chat = chat.add_mutually_exclusive_group()
    origen_chat.add_argument("--proyecto", type=Path, help="Proyecto de entrada")
    origen_chat.add_argument("--nuevo", metavar="NOMBRE", help="Crea un proyecto vacío")
    chat.add_argument("--salida", type=Path, help="Ruta del proyecto resultante")
    chat.add_argument("--mensaje", help="Un solo mensaje y termina")
    chat.add_argument("--max-turnos", type=int, default=8)

    args = parser.parse_args(argv)

    if args.comando == "herramientas":
        herramientas = describir()
        if args.json:
            print(json.dumps(herramientas, ensure_ascii=False, indent=2))
        else:
            for herramienta in herramientas:
                print(f"{herramienta['name']}: {herramienta['description']}")
        return 0

    if args.comando == "validar":
        try:
            agente = Agente.desde_archivo(args.proyecto)
        except (ProjectError, OSError) as exc:
            print(f"Error al cargar el proyecto: {exc}")
            return 2
        return 0 if _imprimir_validacion(agente.proyecto) else 1

    agente = _abrir_agente(args, parser)
    if agente is None:
        return 2

    if args.comando == "chat":
        clave = os.environ.get("CADBIM_LLM_KEY")
        if not clave:
            print(
                "Falta CADBIM_LLM_KEY (opcionales: CADBIM_LLM_URL y "
                "CADBIM_LLM_MODEL)."
            )
            return 2
        proveedor = ProveedorOpenAI(
            clave,
            base_url=os.environ.get("CADBIM_LLM_URL", "https://api.openai.com/v1"),
            model=os.environ.get("CADBIM_LLM_MODEL", "gpt-4o-mini"),
        )
        conversacion = Chat(agente, proveedor, max_turnos=args.max_turnos)
        try:
            if args.mensaje:
                print(conversacion.enviar(args.mensaje))
            else:
                while True:
                    try:
                        linea = input("> ")
                    except EOFError:
                        break
                    if not linea.strip():
                        continue
                    if linea.strip().lower() in {"salir", "exit", "quit"}:
                        break
                    print(conversacion.enviar(linea))
                    if args.salida:
                        agente.guardar(args.salida)
        except (ErrorProveedor, ErrorChat) as exc:
            print(f"Error de conversación: {exc}")
            return 2
        conforme = _imprimir_validacion(agente.proyecto)
        if args.salida:
            agente.guardar(args.salida)
            print(f"proyecto: {args.salida}")
        return 0 if conforme else 1

    try:
        llamadas = _cargar_plan(args.plan)
        agente.aplicar_plan(llamadas)
    except (ValueError, ErrorHerramienta, OSError) as exc:
        print(f"Plan rechazado: {exc}")
        return 2

    print(f"Plan aplicado: {len(llamadas)} llamada(s).")
    conforme = _imprimir_validacion(agente.proyecto)
    if args.salida and not args.dry_run:
        agente.guardar(args.salida)
        print(f"proyecto: {args.salida}")
    return 0 if conforme else 1


if __name__ == "__main__":
    raise SystemExit(main())
