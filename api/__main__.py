"""Servidor local del editor web: ``python -m api``."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from ai.project import proyecto_nuevo
from api.app import create_app
from core.model.loader import ProjectError, load_project


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="api",
        description="Editor web local de CADBIMElectri (FastAPI + uvicorn).",
    )
    origen = parser.add_mutually_exclusive_group()
    origen.add_argument("--proyecto", help="archivo JSON a editar")
    origen.add_argument("--nuevo", metavar="NOMBRE", help="crea un proyecto vacío")
    parser.add_argument("--host", default="127.0.0.1", help="interfaz de escucha")
    parser.add_argument("--port", type=int, default=8000, help="puerto (8000)")
    parser.add_argument(
        "--salida", default="salida/web", help="carpeta de exportaciones"
    )
    args = parser.parse_args(argv)

    proyecto = None
    if args.proyecto:
        try:
            proyecto = load_project(args.proyecto)
        except (OSError, ProjectError) as exc:
            print(f"ERROR: no se pudo cargar '{args.proyecto}': {exc}")
            return 2
    elif args.nuevo:
        proyecto = proyecto_nuevo(args.nuevo)

    try:
        import uvicorn
    except ImportError:
        print("ERROR: falta uvicorn; instale el extra 'cadbimelectri[api]'")
        return 2

    app = create_app(proyecto, salida=Path(args.salida))
    if args.host in {"0.0.0.0", "::"}:
        print(f"Escuchando en http://{args.host}:{args.port} (red local)")
        print("Advertencia: la API no tiene autenticación; úsela solo en una red de confianza.")
    else:
        print(f"Editor en http://{args.host}:{args.port}")
    uvicorn.run(app, host=args.host, port=args.port)
    return 0


if __name__ == "__main__":
    sys.exit(main())
