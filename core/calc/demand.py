"""Demanda de la instalación.

La NBR 5410 no fija factores de demanda: los define la concesionaria (o el
proyectista) según el tipo de suministro. Este módulo aplica factores declarados
explícitamente y avisa cuando usa los valores sugeridos, que son solo un punto de
partida y no un requisito normativo.
"""
from __future__ import annotations

from typing import Any

from core.calc.load_schedule import load_schedule

FACTORES_SUGERIDOS = {"iluminacion": 1.0, "tug": 0.8, "tue": 1.0}

ADVERTENCIA_FACTORES = (
    "Los factores de demanda no provienen de la NBR 5410: son sugeridos y deben "
    "confirmarse con la concesionaria o con el proyectista"
)


def demanda(
    project: dict[str, Any],
    factores: dict[str, float] | None = None,
) -> dict[str, Any]:
    """Potencia instalada, demanda por tipo y demanda total (VA)."""
    propios = factores is not None
    factores = dict(FACTORES_SUGERIDOS if factores is None else factores)
    warnings: list[str] = []
    if not propios:
        warnings.append(ADVERTENCIA_FACTORES)

    for tipo, factor in factores.items():
        if not 0 <= factor <= 1:
            raise ValueError(f"El factor de demanda de '{tipo}' debe estar entre 0 y 1")

    cuadro = load_schedule(project)
    warnings.extend(cuadro["warnings"])

    por_tipo: dict[str, dict[str, float]] = {}
    for c in cuadro["circuits"]:
        tipo = c["type"]
        if tipo not in factores:
            warnings.append(f"Circuito '{c['id']}': tipo '{tipo}' sin factor de demanda; se usa 1.0")
        factor = factores.get(tipo, 1.0)
        acumulado = por_tipo.setdefault(tipo, {"instalada_va": 0.0, "demanda_va": 0.0, "factor": factor})
        acumulado["instalada_va"] += c["power_va"]
        acumulado["demanda_va"] += c["power_va"] * factor

    instalada = sum(v["instalada_va"] for v in por_tipo.values())
    total = sum(v["demanda_va"] for v in por_tipo.values())

    return {
        "por_tipo": por_tipo,
        "instalada_va": instalada,
        "demanda_va": total,
        "factor_global": round(total / instalada, 3) if instalada else None,
        "warnings": warnings,
    }
