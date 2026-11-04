"""Lista de materiales a partir del dimensionamiento.

Solo cuantifica lo que el proyecto declara. No agrega desperdicio de obra salvo que
se pida con `margen_percent`, y no inventa longitudes: los circuitos sin longitud
quedan fuera de la lista de cables con una advertencia.
"""
from __future__ import annotations

from typing import Any

from core.calc.protections import clases_dps, requisitos_dr


def _cable(c: dict[str, Any]) -> tuple:
    return (
        c["material"],
        c["insulation"],
        c["section_mm2"],
        c["phases"] + 1,
    )


def lista_materiales(
    project: dict[str, Any],
    dimensionado: dict[str, Any],
    *,
    margen_percent: float = 0.0,
) -> dict[str, Any]:
    if margen_percent < 0:
        raise ValueError("El margen no puede ser negativo")
    warnings: list[str] = []
    factor = 1 + margen_percent / 100

    cables: dict[tuple, float] = {}
    for c in dimensionado["circuits"]:
        if c["length_m"] is None:
            warnings.append(
                f"Circuito '{c['id']}' sin longitud: no entra en la lista de cables"
            )
            continue
        clave = _cable(c)
        cables[clave] = cables.get(clave, 0.0) + c["length_m"] * factor

    items = []
    for (material, aislacion, seccion, n), metros in sorted(cables.items()):
        items.append(
            {
                "tipo": "cable",
                "descripcion": f"Cable {material} {aislacion} {n}x{seccion:g} mm²",
                "cantidad": round(metros, 2),
                "unidad": "m",
            }
        )

    disyuntores: dict[int, int] = {}
    for c in dimensionado["circuits"]:
        if c["breaker_a"] is not None:
            disyuntores[c["breaker_a"]] = disyuntores.get(c["breaker_a"], 0) + 1
    for amperios, cantidad in sorted(disyuntores.items()):
        items.append(
            {
                "tipo": "disyuntor",
                "descripcion": f"Disyuntor termomagnético {amperios} A",
                "cantidad": cantidad,
                "unidad": "u",
            }
        )

    dr = requisitos_dr(project)
    if dr:
        items.append(
            {
                "tipo": "dr",
                "descripcion": "Dispositivo diferencial residual 2P 30 mA tipo AC",
                "cantidad": len(dr),
                "unidad": "u",
            }
        )

    clases = clases_dps(project["project"].get("supply"))
    for clase in clases:
        nota = "" if clase != "III" else " (uno por equipo sensible)"
        items.append(
            {
                "tipo": "dps",
                "descripcion": f"DPS clase {clase}{nota}",
                "cantidad": 1,
                "unidad": "u",
            }
        )
        if clase == "III":
            warnings.append("Los DPS clase III se cuentan por equipo sensible, no por tablero")

    if project["panels"]:
        items.append(
            {
                "tipo": "tablero",
                "descripcion": "Tablero de distribución",
                "cantidad": len(project["panels"]),
                "unidad": "u",
            }
        )

    return {"items": items, "warnings": warnings}
