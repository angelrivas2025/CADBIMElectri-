"""Caminos mínimos sobre la red (ADR 0004).

Dijkstra con desempate lexicográfico por los ids de los tramos: dos rutas de
igual longitud siempre eligen la misma, de modo que el resultado es reproducible.
Solo se rutea sobre los segmentos declarados; no se generan trazados.
"""
from __future__ import annotations

import heapq
from typing import Any

from core.net.graph import RedInvalida


def camino_minimo(
    grafo: dict[str, Any], origen: str, destino: str
) -> dict[str, Any] | None:
    """Ruta de menor longitud entre dos nodos, o None si no hay camino."""
    adyacencia = grafo["adjacency"]
    if origen not in adyacencia:
        raise RedInvalida(f"Nodo de origen inexistente '{origen}'")
    if destino not in adyacencia:
        raise RedInvalida(f"Nodo de destino inexistente '{destino}'")

    pendientes: list[tuple[float, tuple[str, ...], str]] = [(0.0, (), origen)]
    visitados: set[str] = set()
    while pendientes:
        distancia, camino, nodo = heapq.heappop(pendientes)
        if nodo in visitados:
            continue
        visitados.add(nodo)
        if nodo == destino:
            return {"segments": list(camino), "length_m": distancia}
        for vecino, tramo, longitud in adyacencia[nodo]:
            if vecino not in visitados:
                heapq.heappush(
                    pendientes, (distancia + longitud, camino + (tramo,), vecino)
                )
    return None


def _indices(grafo: dict[str, Any]) -> tuple[dict[str, str], dict[str, str]]:
    paneles: dict[str, str] = {}
    cargas: dict[str, str] = {}
    for nodo in grafo["nodes"].values():
        if nodo["type"] == "panel":
            paneles[nodo["ref"]] = nodo["id"]
        elif nodo["type"] == "load":
            cargas[nodo["ref"]] = nodo["id"]
    return paneles, cargas


def rutas_circuitos(
    project: dict[str, Any], grafo: dict[str, Any]
) -> tuple[dict[str, dict[str, Any]], list[str]]:
    """Ruta tablero → carga de cada circuito, con errores de red."""
    paneles, cargas = _indices(grafo)
    rutas: dict[str, dict[str, Any]] = {}
    errores: list[str] = []
    for circuito in project["circuits"]:
        cid = circuito["id"]
        panel_id = circuito["panel"]
        origen = paneles.get(panel_id)
        destino = cargas.get(cid)
        if origen is None:
            errores.append(f"red: el tablero '{panel_id}' no tiene nodo panel")
            continue
        if destino is None:
            errores.append(f"red: el circuito '{cid}' no tiene nodo load")
            continue
        camino = camino_minimo(grafo, origen, destino)
        if camino is None:
            errores.append(
                f"red: sin camino entre el tablero '{panel_id}' y la carga del circuito '{cid}'"
            )
            continue
        rutas[cid] = {"panel_node": origen, "load_node": destino, **camino}
    return rutas, errores


def rutas_alimentadores(
    project: dict[str, Any], grafo: dict[str, Any]
) -> tuple[dict[str, dict[str, Any]], list[str]]:
    """Ruta suministro → cada tablero."""
    paneles, _ = _indices(grafo)
    suministros = [
        nodo["id"] for nodo in grafo["nodes"].values() if nodo["type"] == "supply"
    ]
    if len(suministros) != 1:
        return {}, [f"red: se esperaba un nodo supply y hay {len(suministros)}"]

    rutas: dict[str, dict[str, Any]] = {}
    errores: list[str] = []
    for panel in project["panels"]:
        pid = panel["id"]
        destino = paneles.get(pid)
        if destino is None:
            errores.append(f"red: el tablero '{pid}' no tiene nodo panel")
            continue
        camino = camino_minimo(grafo, suministros[0], destino)
        if camino is None:
            errores.append(
                f"red: sin camino entre el suministro y el tablero '{pid}'"
            )
            continue
        rutas[pid] = {"supply_node": suministros[0], "panel_node": destino, **camino}
    return rutas, errores


def circuitos_por_tramo(rutas: dict[str, dict[str, Any]]) -> dict[str, list[str]]:
    """Circuitos que pasan por cada tramo, ordenados para reproducibilidad."""
    compartidos: dict[str, set[str]] = {}
    for cid, ruta in rutas.items():
        for sid in ruta["segments"]:
            compartidos.setdefault(sid, set()).add(cid)
    return {sid: sorted(cids) for sid, cids in sorted(compartidos.items())}


def agrupamiento_por_circuito(rutas: dict[str, dict[str, Any]]) -> dict[str, int]:
    """Máximo de circuitos distintos que comparten un tramo de la ruta."""
    compartidos = circuitos_por_tramo(rutas)
    return {
        cid: max((len(compartidos[sid]) for sid in ruta["segments"]), default=1)
        for cid, ruta in rutas.items()
    }
