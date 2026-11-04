"""Previsión de cargas mínimas por ambiente (NBR 5410 9.5.2, uso residencial).

Reglas implementadas (ver core/norms/nbr5410/data/previsao_cargas_minimas.csv):

Iluminación (9.5.2.1)
- Todo ambiente debe tener al menos un punto de luz.
- Hasta 6 m²: 100 VA. Por encima, 60 VA por cada 4 m² completos excedentes.

TUG (9.5.2.2)
- Sala, dormitorio y otros: 1 toma cada 5 m o fracción de perímetro (100 VA);
  hasta 6 m² basta 1 toma de 100 VA.
- Cocina y servicio: 1 toma cada 3,5 m o fracción (mínimo 2); 600 VA cada una de
  las tres primeras y 100 VA las siguientes.
- Baño: 1 toma de 600 VA junto al lavatorio, fuera de la zona del box.
- Garaje: 1 toma de 100 VA.

El exterior queda a criterio del proyectista y la norma no fija mínimo.

Nota: solo se implementa el uso residencial. Las filas comerciales del CSV se
conservan como referencia para cuando exista el tipo de ambiente correspondiente.
"""
from __future__ import annotations

from math import ceil, hypot
from typing import Any

TIPOS_MOJADOS = {"cocina", "servicio"}

POTENCIA_TUG_SIMPLE_VA = 100
POTENCIA_TUG_MOJADA_VA = 600
TUG_MOJADAS_CON_600 = 3


def area_perimetro(polygon: list[list[float]]) -> tuple[float, float]:
    """Área (shoelace) y perímetro de un polígono cerrado implícitamente."""
    if len(polygon) < 3:
        raise ValueError("El polígono necesita al menos 3 vértices")
    area = 0.0
    perimetro = 0.0
    for i, (x1, y1) in enumerate(polygon):
        x2, y2 = polygon[(i + 1) % len(polygon)]
        area += x1 * y2 - x2 * y1
        perimetro += hypot(x2 - x1, y2 - y1)
    return abs(area) / 2, perimetro


def prever_iluminacion(area_m2: float) -> int:
    """Potencia mínima de iluminación en VA."""
    if area_m2 <= 6:
        return 100
    bloques = int((area_m2 - 6) // 4)
    return 100 + 60 * bloques


def prever_tug(tipo: str, area_m2: float, perimetro_m: float) -> dict[str, int]:
    """Cantidad y potencia mínima de tomas de uso general del ambiente."""
    if tipo in TIPOS_MOJADOS:
        n = max(ceil(perimetro_m / 3.5), 2)
        potencia = POTENCIA_TUG_MOJADA_VA * min(n, TUG_MOJADAS_CON_600)
        potencia += POTENCIA_TUG_SIMPLE_VA * max(n - TUG_MOJADAS_CON_600, 0)
        return {"points": n, "power_va": potencia}
    if tipo == "bano":
        return {"points": 1, "power_va": POTENCIA_TUG_MOJADA_VA}
    if tipo == "externo":
        return {"points": 0, "power_va": 0}
    if tipo == "garaje":
        return {"points": 1, "power_va": POTENCIA_TUG_SIMPLE_VA}
    if area_m2 <= 6:
        return {"points": 1, "power_va": POTENCIA_TUG_SIMPLE_VA}
    n = ceil(perimetro_m / 5)
    return {"points": n, "power_va": POTENCIA_TUG_SIMPLE_VA * n}


def prever_ambiente(room: dict[str, Any]) -> dict[str, Any]:
    area, perimetro = area_perimetro(room["polygon"])
    tug = prever_tug(room["type"], area, perimetro)
    exterior = room["type"] == "externo"
    iluminacion = 0 if exterior else prever_iluminacion(area)
    return {
        "room": room["id"],
        "name": room["name"],
        "type": room["type"],
        "area_m2": round(area, 2),
        "perimeter_m": round(perimetro, 2),
        "lighting_points": 0 if exterior or area <= 0 else 1,
        "lighting_va": iluminacion,
        "tug_points": tug["points"],
        "tug_va": tug["power_va"],
        "total_va": iluminacion + tug["power_va"],
    }


def previsao_cargas(project: dict[str, Any]) -> dict[str, Any]:
    warnings: list[str] = []
    ambientes = []
    for room in project["rooms"]:
        try:
            ambiente = prever_ambiente(room)
        except ValueError as e:
            warnings.append(f"Ambiente '{room['id']}' ignorado: {e}")
            continue
        if ambiente["area_m2"] <= 0:
            warnings.append(f"Ambiente '{room['id']}' tiene área nula; no se prevé carga")
        if room["type"] == "externo":
            warnings.append(
                f"Ambiente '{room['id']}' es exterior: la NBR 5410 no fija mínimo, "
                "queda a criterio del proyectista"
            )
        ambientes.append(ambiente)

    return {
        "rooms": ambientes,
        "total_lighting_va": sum(a["lighting_va"] for a in ambientes),
        "total_tug_va": sum(a["tug_va"] for a in ambientes),
        "total_va": sum(a["total_va"] for a in ambientes),
        "warnings": warnings,
    }


def _puntos_por_ambiente(project: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    por_ambiente: dict[str, list[dict[str, Any]]] = {}
    for p in project["points"]:
        por_ambiente.setdefault(p["room"], []).append(p)
    return por_ambiente


def validar_puntos_minimos(project: dict[str, Any]) -> list[str]:
    """Contrasta los puntos declarados con el mínimo normativo por ambiente."""
    problemas: list[str] = []
    por_ambiente = _puntos_por_ambiente(project)
    for room in project["rooms"]:
        try:
            minimo = prever_ambiente(room)
        except ValueError:
            continue
        tipo = room["type"]
        declarados = por_ambiente.get(room["id"], [])
        luces = [p for p in declarados if p["type"] == "luminaria"]
        tug = [p for p in declarados if p["type"] == "tug"]

        if minimo["lighting_points"] and len(luces) < minimo["lighting_points"]:
            problemas.append(
                f"Ambiente '{room['id']}': tiene {len(luces)} punto(s) de iluminación "
                f"y el mínimo es {minimo['lighting_points']}"
            )
        potencia_luces = sum(p["power"] for p in luces)
        if potencia_luces < minimo["lighting_va"]:
            problemas.append(
                f"Ambiente '{room['id']}': iluminación de {potencia_luces:g} VA "
                f"< mínimo {minimo['lighting_va']} VA ({minimo['area_m2']:g} m²)"
            )

        if len(tug) < minimo["tug_points"]:
            problemas.append(
                f"Ambiente '{room['id']}': tiene {len(tug)} toma(s) de uso general "
                f"y el mínimo es {minimo['tug_points']}"
            )
        potencia_tug = sum(p["power"] for p in tug)
        if potencia_tug < minimo["tug_va"]:
            problemas.append(
                f"Ambiente '{room['id']}': TUG de {potencia_tug:g} VA "
                f"< mínimo {minimo['tug_va']} VA"
            )

        if tipo in TIPOS_MOJADOS:
            exigidas = min(TUG_MOJADAS_CON_600, minimo["tug_points"])
            grandes = [p for p in tug if p["power"] >= POTENCIA_TUG_MOJADA_VA]
            if len(grandes) < exigidas:
                problemas.append(
                    f"Ambiente '{room['id']}': {exigidas} toma(s) deben ser de "
                    f"{POTENCIA_TUG_MOJADA_VA} VA y hay {len(grandes)}"
                )
        elif tipo == "bano":
            if not any(p["power"] >= POTENCIA_TUG_MOJADA_VA for p in tug):
                problemas.append(
                    f"Ambiente '{room['id']}': baño sin toma de "
                    f"{POTENCIA_TUG_MOJADA_VA} VA junto al lavatorio"
                )

    return problemas
