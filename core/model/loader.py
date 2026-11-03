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
    return issues


def load_project(path: str | Path) -> dict[str, Any]:
    project = json.loads(Path(path).read_text(encoding="utf-8"))
    issues = schema_issues(project)
    if not issues:  # las referencias solo se revisan si la estructura es válida
        issues = reference_issues(project)
    if issues:
        raise ProjectError(issues)
    return project
