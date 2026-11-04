"""Agrupación de puntos en circuitos (NBR 5410 9.5.3, uso residencial).

Reglas de división:
- iluminación y TUG siempre en circuitos separados;
- cocina y área de servicio con circuito(s) exclusivo(s);
- cada TUE en un circuito terminal propio;
- al menos 1 circuito terminal por cada 60 m² o fracción;
- recomendación (no obligación): no superar 8 puntos por circuito.

`sugerir_circuitos` propone una división determinista y reparte las fases buscando
equilibrio; el motor la valida después, igual que validaría una propuesta de la IA.
"""
from __future__ import annotations

from math import ceil
from typing import Any

from core.calc.load_forecast import area_perimetro
from core.calc.load_schedule import FASES_POR_SISTEMA

TIPOS_MOJADOS = {"cocina", "servicio"}
MAX_PUNTOS_RECOMENDADO = 8
AREA_POR_CIRCUITO_M2 = 60

TIPO_PUNTO_A_CIRCUITO = {
    "luminaria": "iluminacion",
    "interruptor": "iluminacion",
    "tug": "tug",
    "tue": "tue",
}


def _ambientes(project: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {r["id"]: r for r in project["rooms"]}


def _puntos_de_circuito(project: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    por_circuito: dict[str, list[dict[str, Any]]] = {c["id"]: [] for c in project["circuits"]}
    for p in project["points"]:
        if p.get("circuit") in por_circuito:
            por_circuito[p["circuit"]].append(p)
    return por_circuito


def validar_agrupamiento(project: dict[str, Any]) -> list[str]:
    problemas: list[str] = []
    ambientes = _ambientes(project)
    por_circuito = _puntos_de_circuito(project)

    for c in project["circuits"]:
        puntos = por_circuito[c["id"]]
        tipos = {p["type"] for p in puntos} - {"tablero"}
        esperado = c["type"]
        permitidos = {t for t, circuito in TIPO_PUNTO_A_CIRCUITO.items() if circuito == esperado}
        mezclados = tipos - permitidos
        if mezclados:
            problemas.append(
                f"Circuito '{c['id']}' ({esperado}) contiene puntos de tipo "
                f"{sorted(mezclados)}"
            )

        tues = [p for p in puntos if p["type"] == "tue"]
        if len(tues) > 1:
            problemas.append(
                f"Circuito '{c['id']}' tiene {len(tues)} TUE; cada uno exige circuito propio"
            )

        if esperado == "tug" and puntos:
            salas = {p["room"] for p in puntos}
            mojadas = {r for r in salas if ambientes.get(r, {}).get("type") in TIPOS_MOJADOS}
            if mojadas:
                if len(salas) > 1:
                    problemas.append(
                        f"Circuito '{c['id']}': la cocina/servicio ({', '.join(sorted(mojadas))}) "
                        "debe tener circuito exclusivo y comparte con otros ambientes"
                    )
                if len(mojadas) > 1:
                    problemas.append(
                        f"Circuito '{c['id']}': mezcla cocina/servicio de varios ambientes "
                        f"({', '.join(sorted(mojadas))})"
                    )

    total_area = 0.0
    for room in project["rooms"]:
        try:
            total_area += area_perimetro(room["polygon"])[0]
        except ValueError:
            continue
    minimos = ceil(total_area / AREA_POR_CIRCUITO_M2) if total_area > 0 else 0
    con_puntos = sum(1 for c in project["circuits"] if por_circuito[c["id"]])
    if con_puntos < minimos:
        problemas.append(
            f"Hay {con_puntos} circuito(s) terminal(es) para {total_area:.1f} m²; "
            f"el mínimo es {minimos} (1 por cada {AREA_POR_CIRCUITO_M2} m²)"
        )

    return problemas


def recomendaciones_agrupamiento(project: dict[str, Any]) -> list[str]:
    por_circuito = _puntos_de_circuito(project)
    avisos = []
    for c in project["circuits"]:
        n = len([p for p in por_circuito[c["id"]] if p["type"] != "tablero"])
        if n > MAX_PUNTOS_RECOMENDADO:
            avisos.append(
                f"Circuito '{c['id']}' tiene {n} puntos; se recomienda no superar "
                f"{MAX_PUNTOS_RECOMENDADO}"
            )
    return avisos


def _repartir(puntos: list[dict[str, Any]], tamano: int) -> list[list[dict[str, Any]]]:
    return [puntos[i:i + tamano] for i in range(0, len(puntos), tamano)]


def sugerir_circuitos(project: dict[str, Any]) -> dict[str, Any]:
    """Propuesta determinista de circuitos monofásicos equilibrados entre fases."""
    if not project["panels"]:
        raise ValueError("El proyecto no tiene tableros")
    panel = project["panels"][0]["id"]
    fases = FASES_POR_SISTEMA[project["project"]["system"]]
    ambientes = _ambientes(project)

    luces = [p for p in project["points"] if p["type"] in ("luminaria", "interruptor")]
    tues = [p for p in project["points"] if p["type"] == "tue"]
    tugs = [p for p in project["points"] if p["type"] == "tug"]

    grupos: list[tuple[str, list[dict[str, Any]]]] = []
    for i, grupo in enumerate(_repartir(luces, MAX_PUNTOS_RECOMENDADO), 1):
        grupos.append((f"Iluminación {i}", grupo))

    mojadas = sorted(
        {p["room"] for p in tugs if ambientes.get(p["room"], {}).get("type") in TIPOS_MOJADOS}
    )
    for room_id in mojadas:
        grupo = [p for p in tugs if p["room"] == room_id]
        nombre = ambientes[room_id]["name"]
        for i, parte in enumerate(_repartir(grupo, MAX_PUNTOS_RECOMENDADO), 1):
            sufijo = f" {i}" if len(grupo) > MAX_PUNTOS_RECOMENDADO else ""
            grupos.append((f"TUG {nombre}{sufijo}", parte))

    generales = [p for p in tugs if p["room"] not in set(mojadas)]
    for i, grupo in enumerate(_repartir(generales, MAX_PUNTOS_RECOMENDADO), 1):
        grupos.append((f"TUG general {i}" if len(generales) > MAX_PUNTOS_RECOMENDADO else "TUG general", grupo))

    for p in tues:
        grupos.append((f"TUE {p['id']} ({p['room']})", [p]))

    circuitos = []
    asignaciones: dict[str, str] = {}
    carga_fase = {f: 0.0 for f in fases}
    for i, (nombre, puntos) in enumerate(grupos, 1):
        tipo = TIPO_PUNTO_A_CIRCUITO[puntos[0]["type"]]
        va = sum(p["power"] for p in puntos)
        fase = min(fases, key=lambda f: carga_fase[f])
        carga_fase[fase] += va
        cid = f"C{i}"
        circuitos.append(
            {"id": cid, "name": nombre, "type": tipo, "panel": panel, "phase": fase}
        )
        for p in puntos:
            asignaciones[p["id"]] = cid

    for p in project["points"]:
        if p["type"] == "tablero":
            asignaciones[p["id"]] = None
        elif p["id"] not in asignaciones:
            asignaciones[p["id"]] = None

    return {
        "circuits": circuitos,
        "assignments": asignaciones,
        "warnings": [] if grupos else ["No hay puntos que agrupar"],
    }
