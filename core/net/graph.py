"""Grafo no dirigido de la red eléctrica (ADR 0004).

La longitud de cada tramo es la distancia 3D entre sus extremos, sumando los
quiebres declarados en `waypoints`. No se estima nada: si falta una coordenada o
un extremo, la red no se puede interpretar.
"""
from __future__ import annotations

from math import dist
from typing import Any


class RedInvalida(Exception):
    """La red no se puede interpretar como grafo."""


def _xyz(punto: list[float]) -> tuple[float, float, float]:
    if len(punto) != 3:
        raise RedInvalida(
            f"Se esperaban 3 coordenadas [x, y, z] y llegaron {len(punto)}"
        )
    return (float(punto[0]), float(punto[1]), float(punto[2]))


def _posicion(nodo: dict[str, Any]) -> tuple[float, float, float]:
    try:
        x, y = nodo["position"]
        z = nodo["height"]
    except (KeyError, TypeError, ValueError) as e:
        raise RedInvalida(
            f"El nodo '{nodo.get('id', '?')}' no tiene posición y altura completas"
        ) from e
    return (float(x), float(y), float(z))


def longitud_tramo(tramo: dict[str, Any], nodos: dict[str, dict[str, Any]]) -> float:
    """Longitud 3D del tramo, incluidos los quiebres declarados."""
    try:
        origen = _posicion(nodos[tramo["from"]])
        destino = _posicion(nodos[tramo["to"]])
    except KeyError as e:
        raise RedInvalida(
            f"El tramo '{tramo.get('id', '?')}' apunta a un nodo inexistente"
        ) from e
    puntos = [origen, *(_xyz(p) for p in tramo.get("waypoints") or []), destino]
    return sum(dist(a, b) for a, b in zip(puntos, puntos[1:]))


def construir_grafo(project: dict[str, Any]) -> dict[str, Any]:
    red = project.get("network")
    if not red:
        raise RedInvalida("El proyecto no declara red")

    nodos: dict[str, dict[str, Any]] = {}
    for nodo in red.get("nodes", []):
        if nodo["id"] in nodos:
            raise RedInvalida(f"Nodo duplicado '{nodo['id']}'")
        _posicion(nodo)
        nodos[nodo["id"]] = nodo

    adyacencia: dict[str, list[tuple[str, str, float]]] = {nid: [] for nid in nodos}
    tramos: dict[str, dict[str, Any]] = {}
    for tramo in red.get("segments", []):
        sid = tramo["id"]
        if sid in tramos:
            raise RedInvalida(f"Tramo duplicado '{sid}'")
        if tramo["from"] not in nodos or tramo["to"] not in nodos:
            raise RedInvalida(f"El tramo '{sid}' tiene un extremo inexistente")
        if tramo["from"] == tramo["to"]:
            raise RedInvalida(f"El tramo '{sid}' une un nodo consigo mismo")
        longitud = longitud_tramo(tramo, nodos)
        if longitud <= 0:
            raise RedInvalida(f"El tramo '{sid}' tiene longitud nula")
        tramos[sid] = {**tramo, "length_m": longitud}
        adyacencia[tramo["from"]].append((tramo["to"], sid, longitud))
        adyacencia[tramo["to"]].append((tramo["from"], sid, longitud))

    for vecinos in adyacencia.values():
        vecinos.sort(key=lambda v: (v[1], v[0]))

    return {"nodes": nodos, "segments": tramos, "adjacency": adyacencia}
