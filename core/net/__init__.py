"""Red 2.5D: grafo, ruteo, agrupamiento y ocupación (ADR 0004)."""
from core.net.graph import RedInvalida, construir_grafo, longitud_tramo
from core.net.occupancy import verificar_ocupacion
from core.net.report import analizar_red
from core.net.routing import (
    agrupamiento_por_circuito,
    camino_minimo,
    circuitos_por_tramo,
    rutas_alimentadores,
    rutas_circuitos,
)

__all__ = [
    "RedInvalida",
    "agrupamiento_por_circuito",
    "analizar_red",
    "camino_minimo",
    "circuitos_por_tramo",
    "construir_grafo",
    "longitud_tramo",
    "rutas_alimentadores",
    "rutas_circuitos",
    "verificar_ocupacion",
]
