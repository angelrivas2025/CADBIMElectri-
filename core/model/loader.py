"""Carga y validación de proyectos CADBIMElectri."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

SCHEMA_PATH = Path(__file__).with_name("project.schema.json")


class ProjectError(Exception):
    """El proyecto no cumple el esquema o tiene referencias rotas."""

    def __init__(self, issues: list[str]):
        self.issues = issues
        super().__init__("\n".join(issues))


def schema_issues(project: dict[str, Any]) -> list[str]:
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    validator = Draft202012Validator(schema)
    return [
        f"{'/'.join(str(p) for p in e.absolute_path) or '(raíz)'}: {e.message}"
        for e in validator.iter_errors(project)
    ]


def _network_issues(project: dict[str, Any]) -> list[str]:
    """Valida estructura y referencias de la red (ADR 0004)."""
    network = project.get("network")
    if not network:
        return []

    issues: list[str] = []
    nodes = network.get("nodes", [])
    segments = network.get("segments", [])
    node_map: dict[str, dict[str, Any]] = {}
    for node in nodes:
        if node["id"] in node_map:
            issues.append(f"network: nodo '{node['id']}' duplicado")
        node_map[node["id"]] = node

    segment_ids: set[str] = set()
    for segment in segments:
        if segment["id"] in segment_ids:
            issues.append(f"network: tramo '{segment['id']}' duplicado")
        segment_ids.add(segment["id"])

    levels = {nivel["id"] for nivel in project.get("levels", [])}
    panels = {panel["id"]: panel for panel in project.get("panels", [])}
    circuits = {circuito["id"]: circuito for circuito in project.get("circuits", [])}

    supplies = [n for n in nodes if n["type"] == "supply"]
    if len(supplies) != 1:
        issues.append(f"network: se esperaba un nodo supply y hay {len(supplies)}")

    nodos_panel: dict[str, list[str]] = {}
    nodos_carga: dict[str, list[str]] = {}
    for node in nodes:
        if node["level"] not in levels:
            issues.append(
                f"network: nodo '{node['id']}' con nivel inexistente '{node['level']}'"
            )
        tipo = node["type"]
        ref = node.get("ref")
        if tipo == "panel":
            if ref not in panels:
                issues.append(
                    f"network: nodo '{node['id']}' referencia un tablero inexistente '{ref}'"
                )
            else:
                nodos_panel.setdefault(ref, []).append(node["id"])
                if node["level"] != panels[ref]["level"]:
                    issues.append(
                        f"network: nodo '{node['id']}' (tablero {ref}) está en nivel "
                        f"'{node['level']}' y el tablero en '{panels[ref]['level']}'"
                    )
        elif tipo == "load":
            if ref not in circuits:
                issues.append(
                    f"network: nodo '{node['id']}' referencia un circuito inexistente '{ref}'"
                )
            else:
                nodos_carga.setdefault(ref, []).append(node["id"])

    for panel_id in panels:
        nodos = nodos_panel.get(panel_id, [])
        if not nodos:
            issues.append(f"network: tablero '{panel_id}' sin nodo panel")
        elif len(nodos) > 1:
            issues.append(
                f"network: tablero '{panel_id}' tiene {len(nodos)} nodos panel"
            )
    for circuit_id in circuits:
        nodos = nodos_carga.get(circuit_id, [])
        if not nodos:
            issues.append(f"network: circuito '{circuit_id}' sin nodo load")
        elif len(nodos) > 1:
            issues.append(
                f"network: circuito '{circuit_id}' tiene {len(nodos)} nodos load"
            )

    for segment in segments:
        origen = node_map.get(segment["from"])
        destino = node_map.get(segment["to"])
        if origen is None or destino is None:
            faltante = segment["from"] if origen is None else segment["to"]
            issues.append(
                f"network: tramo '{segment['id']}' con extremo inexistente '{faltante}'"
            )
            continue
        if segment["from"] == segment["to"]:
            issues.append(f"network: tramo '{segment['id']}' une un nodo consigo mismo")
        elif (
            origen["level"] != destino["level"]
            and segment["kind"] != "riser"
        ):
            issues.append(
                f"network: tramo '{segment['id']}' une niveles distintos y no es riser"
            )
    return issues


def reference_issues(project: dict[str, Any]) -> list[str]:
    """Revisa ids únicos y referencias entre elementos."""
    issues: list[str] = []
    ids: dict[str, set[str]] = {}
    for key in ("levels", "rooms", "points", "circuits", "panels"):
        seen: set[str] = set()
        for item in project.get(key, []):
            if item["id"] in seen:
                issues.append(f"{key}: id duplicado '{item['id']}'")
            seen.add(item["id"])
        ids[key] = seen

    for r in project.get("rooms", []):
        if r["level"] not in ids["levels"]:
            issues.append(f"room '{r['id']}': nivel inexistente '{r['level']}'")
    for p in project.get("points", []):
        if p["room"] not in ids["rooms"]:
            issues.append(f"point '{p['id']}': ambiente inexistente '{p['room']}'")
        if p.get("circuit") and p["circuit"] not in ids["circuits"]:
            issues.append(f"point '{p['id']}': circuito inexistente '{p['circuit']}'")
    for c in project.get("circuits", []):
        if c["panel"] not in ids["panels"]:
            issues.append(f"circuit '{c['id']}': tablero inexistente '{c['panel']}'")
    for q in project.get("panels", []):
        if q["level"] not in ids["levels"]:
            issues.append(f"panel '{q['id']}': nivel inexistente '{q['level']}'")
    issues.extend(_network_issues(project))
    return issues


def load_project(path: str | Path) -> dict[str, Any]:
    project = json.loads(Path(path).read_text(encoding="utf-8"))
    issues = schema_issues(project)
    if not issues:  # las referencias solo se revisan si la estructura es válida
        issues = reference_issues(project)
    if issues:
        raise ProjectError(issues)
    return project
