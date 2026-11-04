"""Genera todas las salidas de un proyecto en una carpeta."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from exporters.csv_export import cuadro_csv
from exporters.diagram import construir_unifilar
from exporters.pdf import informe_pdf
from exporters.svg import escribir_svg


def exportar_todo(
    project: dict[str, Any], informe: dict[str, Any], salida: str | Path
) -> dict[str, Path]:
    destino = Path(salida)
    destino.mkdir(parents=True, exist_ok=True)
    diagrama = construir_unifilar(project, informe)
    return {
        "svg": escribir_svg(diagrama, destino / "unifilar.svg"),
        "pdf": informe_pdf(project, informe, destino / "informe.pdf"),
        "csv": cuadro_csv(project, informe, destino / "cuadro_cargas.csv"),
    }
