"""Capacidad de conducción de corriente a partir de una tabla cargada desde CSV.

La tabla NO viene incluida (ver data/README.md). Si falta algún dato, el motor se
detiene con un error en lugar de inventar valores.
"""
from __future__ import annotations

import csv
from pathlib import Path
from typing import Iterable

DATA_DIR = Path(__file__).with_name("data")
TABLA_COBRE_PVC = DATA_DIR / "ampacidad_cobre_pvc.csv"

# Secciones nominales comerciales en mm² (serie normalizada de conductores).
SECCIONES_COMERCIALES = [
    0.5, 0.75, 1, 1.5, 2.5, 4, 6, 10, 16, 25, 35, 50, 70, 95, 120, 150, 185, 240, 300,
]

Tabla = dict[tuple[str, int], dict[float, float]]  # (metodo, n_conductores) -> {seccion: A}


class TablaIncompleta(Exception):
    """No hay datos suficientes en la tabla para responder."""


def cargar_tabla(path: str | Path = TABLA_COBRE_PVC) -> Tabla:
    tabla: Tabla = {}
    with open(path, encoding="utf-8", newline="") as f:
        for fila in csv.DictReader(f):
            clave = (fila["metodo"].strip().upper(), int(fila["n_conductores"]))
            tabla.setdefault(clave, {})[float(fila["seccion_mm2"])] = float(fila["corriente_a"])
    return tabla


def validar_tabla(tabla: Tabla) -> list[str]:
    """Detecta errores típicos de transcripción. No sustituye la verificación humana."""
    problemas: list[str] = []
    for (metodo, n), filas in tabla.items():
        previa: tuple[float, float] | None = None
        for seccion in sorted(filas):
            corriente = filas[seccion]
            if seccion not in SECCIONES_COMERCIALES:
                problemas.append(f"{metodo}/{n}: sección {seccion} mm² no es comercial")
            if corriente <= 0:
                problemas.append(f"{metodo}/{n}: corriente no positiva en {seccion} mm²")
            if previa and corriente <= previa[1]:
                problemas.append(
                    f"{metodo}/{n}: la corriente no crece entre {previa[0]} y {seccion} mm²"
                )
            previa = (seccion, corriente)
        if n == 3 and (metodo, 2) in tabla:
            for seccion, c3 in filas.items():
                c2 = tabla[(metodo, 2)].get(seccion)
                if c2 is not None and c3 > c2:
                    problemas.append(
                        f"{metodo}: con 3 conductores ({c3} A) supera a 2 conductores ({c2} A) en {seccion} mm²"
                    )
    return problemas


def seleccionar_seccion(
    corriente_a: float, metodo: str, n_conductores: int, tabla: Tabla
) -> float:
    """Menor sección comercial cuya capacidad es >= corriente_a (ya corregida)."""
    filas = tabla.get((metodo.strip().upper(), n_conductores))
    if not filas:
        raise TablaIncompleta(
            f"No hay datos para método {metodo} con {n_conductores} conductores cargados. "
            "Llena core/norms/nbr5410/data/ampacidad_cobre_pvc.csv (ver data/README.md)."
        )
    for seccion in sorted(filas):
        if filas[seccion] >= corriente_a:
            return seccion
    raise TablaIncompleta(
        f"Ninguna sección de la tabla soporta {corriente_a} A (máximo cargado: {max(filas.values())} A)"
    )


def secciones_faltantes(tabla: Tabla, metodo: str, n: int, requeridas: Iterable[float]) -> list[float]:
    filas = tabla.get((metodo.strip().upper(), n), {})
    return [s for s in requeridas if s not in filas]
