"""Corriente de proyecto por circuito.

v0.1: solo circuitos de una fase (I = P / V, con V fase-neutro del proyecto).
Los circuitos en varias fases quedan sin corriente y con una advertencia,
porque requieren conocer la tensión entre fases del sistema.
"""
from __future__ import annotations

from typing import Any

from core.calc.load_schedule import load_schedule


def circuit_currents(project: dict[str, Any]) -> dict[str, Any]:
    tension = project["project"]["voltage"]
    cuadro = load_schedule(project)
    warnings = list(cuadro["warnings"])
    resultado = []

    for c in cuadro["circuits"]:
        corriente = None
        fase = c["phase"]
        if fase and len(fase) == 1:
            corriente = round(c["power_va"] / tension, 2)
        elif fase:
            warnings.append(
                f"Circuito '{c['id']}' en varias fases ({fase}): corriente no calculada en v0.1"
            )
        resultado.append({**c, "current_a": corriente})

    return {"circuits": resultado, "warnings": warnings}
