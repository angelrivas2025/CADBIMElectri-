"""Fábrica de proyectos vacíos para las CLI y la API."""
from __future__ import annotations


def proyecto_nuevo(nombre: str, *, voltage: float = 127.0) -> dict:
    return {
        "schemaVersion": "0.2",
        "project": {
            "name": nombre,
            "norm": "NBR5410",
            "voltage": voltage,
            "system": "monofasico" if voltage <= 127 else "bifasico",
        },
        "levels": [{"id": "N0", "name": "Nivel 0", "elevation": 0}],
        "rooms": [],
        "points": [],
        "circuits": [],
        "panels": [],
    }
