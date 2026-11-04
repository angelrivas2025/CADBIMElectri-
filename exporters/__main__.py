"""CLI: python -m exporters examples/casa-conforme.json --salida salida"""
from __future__ import annotations

import argparse
from pathlib import Path

from core.calc.validate import validar_proyecto
from core.model.loader import ProjectError, load_project
from exporters.export import exportar_todo


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m exporters",
        description="Genera unifilar SVG, cuadro de cargas CSV, informe PDF y modelo IFC.",
    )
    parser.add_argument("proyecto", type=Path, help="Ruta al project.json")
    parser.add_argument(
        "--salida", type=Path, default=Path("salida"), help="Carpeta de salida"
    )
    args = parser.parse_args(argv)

    try:
        project = load_project(args.proyecto)
    except ProjectError as e:
        print(f"Error al cargar el proyecto: {e}")
        return 2

    informe = validar_proyecto(project)
    try:
        rutas = exportar_todo(project, informe, args.salida)
    except RuntimeError as e:
        print(f"Error al exportar: {e}")
        return 2

    for nombre, ruta in rutas.items():
        print(f"{nombre}: {ruta}")
    if "ifc" not in rutas:
        print("ifc: omitido (instale 'cadbimelectri[bim]' para exportar el modelo)")
    for error in informe["errores"]:
        print(f"ERROR: {error}")
    if informe["errores"]:
        print(f"El proyecto tiene {len(informe['errores'])} error(es) de cumplimiento.")
        return 1
    print("Proyecto sin errores de cumplimiento.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
