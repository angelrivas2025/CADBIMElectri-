"""Cuadro de cargas en CSV (UTF-8 con BOM para abrir en Excel)."""
from __future__ import annotations

import csv
from pathlib import Path
from typing import Any

COLUMNAS = [
    "ID",
    "Cuadro",
    "Circuito",
    "Tipo",
    "Fase",
    "Puntos",
    "VA",
    "Corriente_A",
    "Longitud_m",
    "Seccion_mm2",
    "Conductores",
    "Material",
    "Aislacion",
    "In_A",
    "Curva",
    "Caida_pct",
    "DR",
    "Metodo",
    "Variante",
]


def cuadro_csv(
    project: dict[str, Any], informe: dict[str, Any], ruta: str | Path
) -> Path:
    dr_por_circuito = (informe.get("protecciones") or {}).get("dr_por_circuito") or {}
    circuitos = sorted(
        (informe.get("dimensionamiento") or {}).get("circuits") or [],
        key=lambda c: (c.get("panel") or "", c["id"]),
    )
    destino = Path(ruta)
    destino.parent.mkdir(parents=True, exist_ok=True)
    with destino.open("w", newline="", encoding="utf-8-sig") as archivo:
        escritor = csv.DictWriter(archivo, fieldnames=COLUMNAS, delimiter=";")
        escritor.writeheader()
        for c in circuitos:
            escritor.writerow(
                {
                    "ID": c["id"],
                    "Cuadro": c.get("panel") or "",
                    "Circuito": c["name"],
                    "Tipo": c["type"],
                    "Fase": c.get("phase") or "",
                    "Puntos": c.get("points", 0),
                    "VA": f"{c.get('power_va') or 0:.0f}",
                    "Corriente_A": f"{c['current_a']:.2f}",
                    "Longitud_m": "" if c.get("length_m") is None else f"{c['length_m']:g}",
                    "Seccion_mm2": f"{c['section_mm2']:g}",
                    "Conductores": c["phases"] + 1,
                    "Material": c["material"],
                    "Aislacion": c["insulation"],
                    "In_A": c.get("breaker_a") or "",
                    "Curva": c.get("breaker_curve") or "",
                    "Caida_pct": (
                        "" if c.get("voltage_drop_pct") is None
                        else f"{c['voltage_drop_pct']:.2f}"
                    ),
                    "DR": "Si" if c["id"] in dr_por_circuito else "No",
                    "Metodo": c.get("method") or "",
                    "Variante": c.get("variant") or "",
                }
            )
    return destino
