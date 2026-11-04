"""Capacidad de conducción de corriente desde las tablas 36 a 39 de la NBR 5410.

Los CSV de data/ se generan con data/build_tables.py a partir del consolidado
verificado en data/source (ver data/SOURCE.md). Si falta un dato, el motor se
detiene con un error en lugar de interpolar o inventar valores.
"""
from __future__ import annotations

import csv
from pathlib import Path
from typing import Iterable

DATA_DIR = Path(__file__).with_name("data")

TABLAS_NORMA = {
    ("Cu", "PVC"): DATA_DIR / "ampacidad_cobre_pvc.csv",
    ("Cu", "XLPE"): DATA_DIR / "ampacidad_cobre_xlpe.csv",
    ("Al", "PVC"): DATA_DIR / "ampacidad_aluminio_pvc.csv",
    ("Al", "XLPE"): DATA_DIR / "ampacidad_aluminio_xlpe.csv",
}
TABLA_COBRE_PVC = TABLAS_NORMA[("Cu", "PVC")]

# Secciones nominales comerciales en mm² (serie normalizada de conductores).
SECCIONES_COMERCIALES = [
    0.5, 0.75, 1.0, 1.5, 2.5, 4.0, 6.0, 10.0, 16.0, 25.0, 35.0, 50.0, 70.0,
    95.0, 120.0, 150.0, 185.0, 240.0, 300.0, 400.0, 500.0, 630.0, 800.0, 1000.0,
]

# La NBR 5410 desdobla F y G según la disposición de los cables. La variante es
# parte de la decisión de proyecto: no se elige por defecto (ver _etiqueta).
VARIANTES = {
    ("F", 2): ("F_JUSTAPOSTO",),
    ("F", 3): ("F_JUSTAPOSTO", "F_TRIFOLIO"),
    ("G", 3): ("G_HORIZONTAL", "G_VERTICAL"),
}
ETIQUETAS_FIJAS = {"A1", "A2", "B1", "B2", "C", "D", "E"}

Tabla = dict[tuple[str, int], dict[float, float]]  # (metodo, n_conductores) -> {seccion: A}


class TablaIncompleta(Exception):
    """No hay datos suficientes en la tabla para responder."""


def _leer_filas(path: Path) -> list[dict[str, str]]:
    with open(path, encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def cargar_tabla(path: str | Path = TABLA_COBRE_PVC) -> Tabla:
    tabla: Tabla = {}
    for fila in _leer_filas(Path(path)):
        clave = (fila["metodo"].strip().upper(), int(fila["n_conductores"]))
        seccion = float(fila["seccion_mm2"])
        corriente = float(fila["corriente_a"])
        filas = tabla.setdefault(clave, {})
        if seccion in filas and filas[seccion] != corriente:
            raise ValueError(
                f"{Path(path).name}: {clave[0]}/{clave[1]} en {seccion} mm² aparece "
                f"con dos valores ({filas[seccion]} y {corriente})"
            )
        filas[seccion] = corriente
    return tabla


def cargar_tabla_norma(material: str = "Cu", aislacion: str = "PVC") -> Tabla:
    clave = (material.capitalize(), aislacion.upper())
    if clave not in TABLAS_NORMA:
        opciones = ", ".join(f"{m}/{a}" for m, a in TABLAS_NORMA)
        raise ValueError(f"No hay tabla para {material}/{aislacion}. Opciones: {opciones}")
    return cargar_tabla(TABLAS_NORMA[clave])


def procedencia(path: str | Path = TABLA_COBRE_PVC) -> dict[str, object]:
    """Tablas de la NBR y material de los que procede el CSV (para trazabilidad)."""
    tablas: set[int] = set()
    materiales: set[str] = set()
    aislaciones: set[str] = set()
    for fila in _leer_filas(Path(path)):
        tablas.add(int(fila["tabla_nbr"]))
        materiales.add(fila["material"].strip())
        aislaciones.add(fila["aislacion"].strip())
    if len(materiales) != 1 or len(aislaciones) != 1:
        raise ValueError(
            f"{Path(path).name} mezcla materiales o aislaciones: {materiales} / {aislaciones}"
        )
    return {
        "tablas_nbr": sorted(tablas),
        "material": materiales.pop(),
        "aislacion": aislaciones.pop(),
        "archivo": Path(path).name,
    }


def _etiqueta(metodo: str, n_conductores: int, variante: str | None = None) -> str:
    metodo = metodo.strip().upper()
    if metodo in ETIQUETAS_FIJAS:
        if variante:
            raise ValueError(f"El método {metodo} no admite variante")
        return metodo
    opciones = VARIANTES.get((metodo, n_conductores))
    if not opciones:
        raise ValueError(f"Método desconocido: {metodo} con {n_conductores} conductores")
    if variante is None:
        if len(opciones) > 1:
            raise ValueError(
                f"El método {metodo} con {n_conductores} conductores exige variante: "
                + " o ".join(opciones)
            )
        return opciones[0]
    etiqueta = variante.strip().upper()
    if etiqueta not in opciones:
        raise ValueError(f"Variante '{variante}' no válida para {metodo}: use {' o '.join(opciones)}")
    return etiqueta


def capacidad(
    metodo: str,
    n_conductores: int,
    seccion_mm2: float,
    tabla: Tabla,
    factor: float = 1.0,
    variante: str | None = None,
) -> float:
    """Capacidad tabulada de la sección, multiplicada por los factores de corrección."""
    filas = tabla.get((_etiqueta(metodo, n_conductores, variante), n_conductores))
    if not filas:
        raise TablaIncompleta(
            f"No hay datos para método {metodo} con {n_conductores} conductores. "
            "Revise core/norms/nbr5410/data (ver SOURCE.md)."
        )
    if seccion_mm2 not in filas:
        raise TablaIncompleta(f"La tabla no tiene {seccion_mm2} mm² para {metodo}/{n_conductores}")
    if factor <= 0:
        raise ValueError("El factor de corrección debe ser positivo")
    return filas[seccion_mm2] * factor


def validar_tabla(tabla: Tabla) -> list[str]:
    """Detecta errores típicos de transcripción. No sustituye la verificación humana."""
    problemas: list[str] = []
    for (metodo, n), filas in tabla.items():
        previa: tuple[float, float] | None = None
        for seccion in sorted(filas):
            corriente = filas[seccion]
            if seccion not in SECCIONES_COMERCIALES:
                problemas.append(f"{metodo}/{n}: sección {seccion:g} mm² no es comercial")
            if corriente <= 0:
                problemas.append(f"{metodo}/{n}: corriente no positiva en {seccion:g} mm²")
            if previa and corriente <= previa[1]:
                problemas.append(
                    f"{metodo}/{n}: la corriente no crece entre {previa[0]:g} y {seccion:g} mm²"
                )
            previa = (seccion, corriente)
        if n == 3 and (metodo, 2) in tabla:
            for seccion, c3 in filas.items():
                c2 = tabla[(metodo, 2)].get(seccion)
                if c2 is not None and c3 > c2:
                    problemas.append(
                        f"{metodo}: con 3 conductores ({c3:g} A) supera a 2 conductores "
                        f"({c2:g} A) en {seccion:g} mm²"
                    )
    return problemas


def seleccionar_seccion(
    corriente_a: float,
    metodo: str,
    n_conductores: int,
    tabla: Tabla,
    *,
    variante: str | None = None,
) -> float:
    """Menor sección comercial cuya capacidad es >= corriente_a (ya corregida)."""
    filas = tabla.get((_etiqueta(metodo, n_conductores, variante), n_conductores))
    if not filas:
        raise TablaIncompleta(
            f"No hay datos para método {metodo} con {n_conductores} conductores cargados. "
            "Revise core/norms/nbr5410/data (ver SOURCE.md)."
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
