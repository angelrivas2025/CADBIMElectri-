"""Lista de materiales en CSV: cables por tipo, protecciones y tableros."""
from __future__ import annotations

import csv
from pathlib import Path
from typing import Any

CABECERAS = ["Tipo", "Descripcion", "Cantidad", "Unidad"]


def materiales_csv(informe: dict[str, Any], ruta: str | Path) -> Path:
    destino = Path(ruta)
    destino.parent.mkdir(parents=True, exist_ok=True)
    items = (informe.get("materiales") or {}).get("items") or []
    with destino.open("w", newline="", encoding="utf-8-sig") as archivo:
        escritor = csv.writer(archivo, delimiter=";")
        escritor.writerow(CABECERAS)
        for item in items:
            escritor.writerow(
                [item["tipo"], item["descripcion"], item["cantidad"], item["unidad"]]
            )
    return destino
