"""Secciones mínimas de conductor por tipo de circuito (NBR 5410 6.2.2, tabla 47).

Para instalaciones residenciales y comerciales con cobre:

- circuitos de iluminación: 1,5 mm²;
- circuitos de fuerza (tomas y equipos): 2,5 mm².

El aluminio no se admite por debajo de 16 mm². Estas secciones mínimas se aplican
aunque la capacidad de conducción permita una sección menor.
"""
from __future__ import annotations

SECCION_MINIMA_ILUMINACION_MM2 = 1.5
SECCION_MINIMA_FUERZA_MM2 = 2.5
SECCION_MINIMA_ALUMINIO_MM2 = 16.0

GRUPOS = {
    "iluminacion": SECCION_MINIMA_ILUMINACION_MM2,
    "tug": SECCION_MINIMA_FUERZA_MM2,
    "tue": SECCION_MINIMA_FUERZA_MM2,
    "general": SECCION_MINIMA_FUERZA_MM2,
}


def seccion_minima(tipo_circuito: str, material: str = "Cu") -> float:
    tipo = tipo_circuito.strip().lower()
    if tipo not in GRUPOS:
        raise ValueError(f"Tipo de circuito desconocido: {tipo_circuito}")
    minima = GRUPOS[tipo]
    if material.capitalize() == "Al":
        return max(minima, SECCION_MINIMA_ALUMINIO_MM2)
    return minima
