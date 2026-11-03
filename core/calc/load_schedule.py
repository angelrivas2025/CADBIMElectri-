"""Cuadro de cargas: potencia instalada por circuito y por fase.

Simplificaciones (v0.1):
- Las potencias están en VA, tal como se declaran en los puntos.
- Un circuito en varias fases (p. ej. "AB") reparte su potencia a partes iguales.
- No aplica factores de demanda ni de simultaneidad (dependen de la norma).
"""
from __future__ import annotations

from typing import Any

FASES_POR_SISTEMA = {
    "monofasico": ["A"],
    "bifasico": ["A", "B"],
    "trifasico": ["A", "B", "C"],
}


def load_schedule(project: dict[str, Any]) -> dict[str, Any]:
    fases = FASES_POR_SISTEMA[project["project"]["system"]]
    warnings: list[str] = []

    circuitos: dict[str, dict[str, Any]] = {
        c["id"]: {
            "id": c["id"],
            "name": c["name"],
            "type": c["type"],
            "panel": c["panel"],
            "phase": c.get("phase"),
            "points": 0,
            "power_va": 0.0,
        }
        for c in project["circuits"]
    }

    for p in project["points"]:
        cid = p.get("circuit")
        if cid is None:
            if p["type"] != "tablero":
                warnings.append(f"Punto '{p['id']}' ({p['type']}) no tiene circuito asignado")
            continue
        circuitos[cid]["points"] += 1
        circuitos[cid]["power_va"] += p["power"]

    por_fase = {f: 0.0 for f in fases}
    for c in circuitos.values():
        fase = c["phase"]
        if not fase:
            warnings.append(f"Circuito '{c['id']}' no tiene fase asignada")
            continue
        invalidas = [f for f in fase if f not in por_fase]
        if invalidas:
            warnings.append(
                f"Circuito '{c['id']}' usa fase(s) {invalidas} que no existen en el sistema {project['project']['system']}"
            )
            continue
        for f in fase:
            por_fase[f] += c["power_va"] / len(fase)

    total = sum(por_fase.values())
    desbalance = None
    if len(fases) > 1 and max(por_fase.values()) > 0:
        mayor, menor = max(por_fase.values()), min(por_fase.values())
        desbalance = round((mayor - menor) / mayor * 100, 1)

    return {
        "circuits": list(circuitos.values()),
        "by_phase_va": por_fase,
        "total_va": total,
        "imbalance_pct": desbalance,
        "warnings": warnings,
    }
