"""Ocupación de canalizaciones (ADR 0004).

Tablas esperadas en `core/norms/nbr5410/data/` (procedencia en SOURCE.md):

- `conductores_diametros.csv`: `material,aislacion,seccion_mm2,diametro_mm`
- `electrodutos_diametros.csv`: `designacion,diametro_interno_mm`
- `limites_ocupacion.csv`: `n_conductores_min,n_conductores_max,limite_pct`

Si falta una tabla o un dato puntual, la etapa **no verifica**: lo informa y no
supone valores. El conteo de conductores sigue la convención del BOM (fases +
neutro); el conductor de protección todavía no se modela.
"""
from __future__ import annotations

import csv
from math import pi
from pathlib import Path
from typing import Any

DATA_DIR = Path(__file__).resolve().parents[1] / "norms" / "nbr5410" / "data"

ARCHIVOS = {
    "conductores": "conductores_diametros.csv",
    "electrodutos": "electrodutos_diametros.csv",
    "limites": "limites_ocupacion.csv",
}


def _filas(path: Path) -> list[dict[str, str]]:
    with open(path, encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def cargar_tablas(data_dir: str | Path = DATA_DIR) -> dict[str, Any]:
    """Carga las tablas disponibles y lista las que faltan."""
    data_dir = Path(data_dir)
    faltantes: list[str] = []

    conductores: dict[tuple[str, str, float], float] = {}
    ruta = data_dir / ARCHIVOS["conductores"]
    if ruta.exists():
        for fila in _filas(ruta):
            clave = (
                fila["material"].strip().capitalize(),
                fila["aislacion"].strip().upper(),
                float(fila["seccion_mm2"]),
            )
            conductores[clave] = float(fila["diametro_mm"])
    else:
        faltantes.append(ARCHIVOS["conductores"])

    electrodutos: dict[str, float] = {}
    ruta = data_dir / ARCHIVOS["electrodutos"]
    if ruta.exists():
        for fila in _filas(ruta):
            electrodutos[fila["designacion"].strip()] = float(
                fila["diametro_interno_mm"]
            )
    else:
        faltantes.append(ARCHIVOS["electrodutos"])

    limites: list[tuple[int, int, float]] = []
    ruta = data_dir / ARCHIVOS["limites"]
    if ruta.exists():
        for fila in _filas(ruta):
            limites.append(
                (
                    int(fila["n_conductores_min"]),
                    int(fila["n_conductores_max"]),
                    float(fila["limite_pct"]),
                )
            )
    else:
        faltantes.append(ARCHIVOS["limites"])

    return {
        "conductores": conductores,
        "electrodutos": electrodutos,
        "limites": limites,
        "faltantes": faltantes,
    }


def conductores_por_circuito(circuito: dict[str, Any]) -> int:
    """Fases + neutro, igual que la lista de cables. Sin fase no se puede contar."""
    fase = circuito.get("phase") or ""
    return len(fase) + 1 if fase else 0


def _limite(n_conductores: int, limites: list[tuple[int, int, float]]) -> float | None:
    for minimo, maximo, limite in limites:
        if minimo <= n_conductores <= maximo:
            return limite
    return None


def _siguiente_medida(
    area_mm2: float, limite_pct: float, actual_mm: float, electrodutos: dict[str, float]
) -> str | None:
    for designacion, interior in sorted(electrodutos.items(), key=lambda x: x[1]):
        if interior <= actual_mm:
            continue
        ocupacion = area_mm2 / (pi * (interior / 2) ** 2) * 100
        if ocupacion <= limite_pct:
            return designacion
    return None


def verificar_ocupacion(
    project: dict[str, Any],
    red: dict[str, Any],
    dimensionado: dict[str, Any],
    *,
    data_dir: str | Path = DATA_DIR,
) -> dict[str, Any]:
    """Ocupación por tramo con las secciones ya dimensionadas."""
    tablas = cargar_tablas(data_dir)
    if tablas["faltantes"]:
        return {
            "verificable": False,
            "tramos": [],
            "errores": [],
            "avisos": [
                "Ocupación no verificable: faltan las tablas "
                + ", ".join(tablas["faltantes"])
                + " en core/norms/nbr5410/data"
            ],
        }

    circuitos = {c["id"]: c for c in project["circuits"]}
    dimensiones = {c["id"]: c for c in dimensionado.get("circuits", [])}
    tramos: list[dict[str, Any]] = []
    errores: list[str] = []
    avisos: list[str] = []
    verificable = True

    for sid, tramo in red["por_tramo"].items():
        circuitos_tramo = tramo["circuits"]
        if not circuitos_tramo:
            continue
        if tramo["kind"] == "tray":
            verificable = False
            tramos.append(
                {
                    **tramo,
                    "estado": "no_verificable",
                    "motivo": "bandeja: la ocupación por ancho no está implementada",
                }
            )
            avisos.append(
                f"Ocupación no verificable en tramo '{sid}': bandeja sin verificación por ancho"
            )
            continue

        n_conductores = 0
        area_mm2 = 0.0
        faltantes: list[str] = []
        for cid in circuitos_tramo:
            circuito = circuitos[cid]
            dimension = dimensiones.get(cid)
            if dimension is None:
                faltantes.append(f"circuito '{cid}' sin dimensionamiento")
                continue
            n = conductores_por_circuito(circuito)
            if not n:
                faltantes.append(f"circuito '{cid}' sin fases")
                continue
            clave = (
                (circuito.get("material") or "Cu").capitalize(),
                (circuito.get("insulation") or "PVC").upper(),
                float(dimension["section_mm2"]),
            )
            diametro = tablas["conductores"].get(clave)
            if diametro is None:
                faltantes.append(
                    f"falta diámetro de {clave[0]}/{clave[1]} {clave[2]:g} mm²"
                )
                continue
            n_conductores += n
            area_mm2 += n * pi * (diametro / 2) ** 2

        interior = tablas["electrodutos"].get(str(tramo["trade_size"]))
        if interior is None:
            faltantes.append(
                f"falta diámetro interno del conducto '{tramo['trade_size']}'"
            )
        limite = _limite(n_conductores, tablas["limites"]) if n_conductores else None
        if n_conductores and limite is None:
            faltantes.append(
                f"falta límite de ocupación para {n_conductores} conductores"
            )

        if faltantes:
            verificable = False
            tramos.append(
                {**tramo, "estado": "no_verificable", "motivo": "; ".join(faltantes)}
            )
            avisos.append(
                f"Ocupación no verificable en tramo '{sid}': " + "; ".join(faltantes)
            )
            continue

        ocupacion_pct = area_mm2 / (pi * (interior / 2) ** 2) * 100
        if ocupacion_pct > limite + 1e-9:
            siguiente = _siguiente_medida(
                area_mm2, limite, interior, tablas["electrodutos"]
            )
            detalle = (
                f"Siguiente medida comercial: {siguiente}"
                if siguiente is not None
                else "No hay una medida mayor en la tabla"
            )
            errores.append(
                f"red: tramo '{sid}' ({tramo['kind']} {tramo['trade_size']}) ocupado "
                f"al {ocupacion_pct:.1f} % (límite {limite:g} %): circuitos "
                f"{', '.join(circuitos_tramo)}. {detalle}"
            )
            tramos.append(
                {
                    **tramo,
                    "estado": "excedido",
                    "ocupacion_pct": round(ocupacion_pct, 1),
                    "limite_pct": limite,
                    "n_conductores": n_conductores,
                }
            )
        else:
            tramos.append(
                {
                    **tramo,
                    "estado": "ok",
                    "ocupacion_pct": round(ocupacion_pct, 1),
                    "limite_pct": limite,
                    "n_conductores": n_conductores,
                }
            )

    return {
        "verificable": verificable,
        "tramos": tramos,
        "errores": errores,
        "avisos": avisos,
    }
