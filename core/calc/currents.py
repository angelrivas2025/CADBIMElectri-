"""Corriente de proyecto por circuito.

La tensión de proyecto (`project.voltage`) es siempre fase-neutro. Para un circuito
entre dos o tres fases la tensión de servicio es la de línea, √3 veces la fase-neutro:

- 1 fase (A, B o C):        I = P / V
- 2 fases (AB, BC o AC):    I = P / (√3 · V)
- 3 fases (ABC):            I = P / (3 · V)
"""
from __future__ import annotations

from math import sqrt
from typing import Any

from core.calc.load_schedule import FASES_POR_SISTEMA, load_schedule

FACTOR_TENSION = {1: 1.0, 2: sqrt(3), 3: 3.0}


def corriente_de_circuito(power_va: float, n_fases: int, tension_fase_v: float) -> float:
    """Corriente de un circuito equilibrado, en A (redondeada a 2 decimales)."""
    if n_fases not in FACTOR_TENSION:
        raise ValueError(f"n_fases debe ser 1, 2 o 3 (recibido: {n_fases})")
    if tension_fase_v <= 0:
        raise ValueError("La tensión de fase debe ser positiva")
    return round(power_va / (FACTOR_TENSION[n_fases] * tension_fase_v), 2)


def tension_de_servicio(tension_fase_v: float, n_fases: int) -> float:
    """Tensión entre bornes del circuito: fase-neutro o de línea."""
    if n_fases not in FACTOR_TENSION:
        raise ValueError(f"n_fases debe ser 1, 2 o 3 (recibido: {n_fases})")
    return tension_fase_v if n_fases == 1 else tension_fase_v * sqrt(3)


def circuit_currents(project: dict[str, Any]) -> dict[str, Any]:
    tension = project["project"]["voltage"]
    fases_sistema = FASES_POR_SISTEMA[project["project"]["system"]]
    cuadro = load_schedule(project)
    warnings = list(cuadro["warnings"])
    resultado = []

    for c in cuadro["circuits"]:
        fase = c["phase"]
        n_fases = len(fase) if fase else 0
        corriente = None
        valido = n_fases > 0 and all(f in fases_sistema for f in fase)
        if valido:
            corriente = corriente_de_circuito(c["power_va"], n_fases, tension)
        resultado.append(
            {
                **c,
                "phases": n_fases,
                "voltage_v": tension_de_servicio(tension, n_fases) if valido else None,
                "current_a": corriente,
            }
        )

    return {"circuits": resultado, "warnings": warnings}
