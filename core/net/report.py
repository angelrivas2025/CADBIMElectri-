"""Resultado integrado de la red: rutas, longitudes y agrupamiento (ADR 0004).

`analizar_red` no dimensiona ni verifica ocupación: solo interpreta el trazado.
La ocupación necesita las secciones ya calculadas y se resuelve en
`core.net.occupancy.verificar_ocupacion`.
"""
from __future__ import annotations

from typing import Any

from core.net.graph import RedInvalida, construir_grafo
from core.net.routing import (
    agrupamiento_por_circuito,
    circuitos_por_tramo,
    rutas_alimentadores,
    rutas_circuitos,
)

UMBRAL_DIFERENCIA_PCT = 5.0


def _sin_red() -> dict[str, Any]:
    return {
        "presente": False,
        "por_circuito": {},
        "alimentadores": {},
        "alimentador_referencia": None,
        "por_tramo": {},
        "errores": [],
        "avisos": [],
    }


def _aviso_diferencia(que: str, declarada: float, calculada: float, pct: float) -> str:
    return (
        f"red: {que} declarada con {declarada:g} m y ruteada con {calculada:.2f} m "
        f"({pct:.1f} % de diferencia); manda la red"
    )


def analizar_red(project: dict[str, Any]) -> dict[str, Any]:
    if not project.get("network"):
        return _sin_red()

    try:
        grafo = construir_grafo(project)
    except RedInvalida as e:
        return {**_sin_red(), "presente": True, "errores": [f"red: {e}"]}

    rutas, errores = rutas_circuitos(project, grafo)
    alimentadores, errores_alimentador = rutas_alimentadores(project, grafo)
    errores.extend(errores_alimentador)

    agrupados = agrupamiento_por_circuito(rutas)
    compartidos = circuitos_por_tramo(rutas)
    circuitos = {c["id"]: c for c in project["circuits"]}
    avisos: list[str] = []

    por_circuito: dict[str, dict[str, Any]] = {}
    for cid, ruta in rutas.items():
        declarada = circuitos[cid].get("length_m")
        diferencia = None
        if declarada is not None:
            diferencia = round(abs(ruta["length_m"] - declarada) / declarada * 100, 1)
            if diferencia > UMBRAL_DIFERENCIA_PCT:
                avisos.append(
                    _aviso_diferencia(
                        f"circuito '{cid}'", declarada, ruta["length_m"], diferencia
                    )
                )
        por_circuito[cid] = {
            **ruta,
            "length_m": round(ruta["length_m"], 2),
            "grouped_circuits": agrupados[cid],
            "declared_length_m": declarada,
            "difference_pct": diferencia,
        }

    por_tramo = {
        sid: {
            "kind": tramo["kind"],
            "trade_size": tramo["trade_size"],
            "length_m": round(tramo["length_m"], 2),
            "circuits": compartidos.get(sid, []),
            "n_circuits": len(compartidos.get(sid, [])),
        }
        for sid, tramo in sorted(grafo["segments"].items())
    }

    referencia = None
    if alimentadores:
        referencia = max(
            alimentadores, key=lambda pid: (alimentadores[pid]["length_m"], pid)
        )
        if len(alimentadores) > 1:
            avisos.append(
                f"red: varios tableros ({len(alimentadores)}); el alimentador se calcula "
                f"con la ruta más larga (tablero '{referencia}')"
            )
        supply = (project.get("project") or {}).get("supply") or {}
        declarada = supply.get("feeder_length_m")
        calculada = alimentadores[referencia]["length_m"]
        if declarada is not None:
            diferencia = abs(calculada - declarada) / declarada * 100
            if diferencia > UMBRAL_DIFERENCIA_PCT:
                avisos.append(
                    _aviso_diferencia("longitud del alimentador", declarada, calculada, diferencia)
                )

    return {
        "presente": True,
        "por_circuito": por_circuito,
        "alimentadores": {
            pid: {**ruta, "length_m": round(ruta["length_m"], 2)}
            for pid, ruta in sorted(alimentadores.items())
        },
        "alimentador_referencia": referencia,
        "por_tramo": por_tramo,
        "errores": errores,
        "avisos": avisos,
    }
