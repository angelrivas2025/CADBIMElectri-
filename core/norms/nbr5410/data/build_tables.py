"""Genera los CSV de ampacidad (formato largo) desde el consolidado verificado.

Uso:
    python core/norms/nbr5410/data/build_tables.py

El consolidado de origen está en data/source/tabelas_36_39_consolidadas.csv y
procede de las tablas 36-39 reproducidas por la guía de dimensionamiento de
Prysmian, contrastadas con el catálogo de Cobrecom (ver SOURCE.md).
No editar los CSV generados a mano: se regeneran desde el origen.
"""
from __future__ import annotations

import csv
from pathlib import Path

DATA = Path(__file__).resolve().parent
ORIGEN = DATA / "source" / "tabelas_36_39_consolidadas.csv"

# (metodo, n_conductores, columna en el consolidado)
COLUMNAS = [
    ("A1", 2, "A1_2c"), ("A1", 3, "A1_3c"),
    ("A2", 2, "A2_2c"), ("A2", 3, "A2_3c"),
    ("B1", 2, "B1_2c"), ("B1", 3, "B1_3c"),
    ("B2", 2, "B2_2c"), ("B2", 3, "B2_3c"),
    ("C", 2, "C_2c"), ("C", 3, "C_3c"),
    ("D", 2, "D_2c"), ("D", 3, "D_3c"),
    ("E", 2, "E_2c"), ("E", 3, "E_3c"),
    ("F_JUSTAPOSTO", 2, "F_2c_just"), ("F_JUSTAPOSTO", 3, "F_3c_just"),
    ("F_TRIFOLIO", 3, "F_3c_trifolio"),
    ("G_HORIZONTAL", 3, "G_horiz"),
    ("G_VERTICAL", 3, "G_vert"),
]

SALIDAS = {
    ("Cu", "PVC"): "ampacidad_cobre_pvc.csv",
    ("Cu", "XLPE"): "ampacidad_cobre_xlpe.csv",
    ("Al", "PVC"): "ampacidad_aluminio_pvc.csv",
    ("Al", "XLPE"): "ampacidad_aluminio_xlpe.csv",
}

ORDEN_SECCION = {s: i for i, s in enumerate([
    0.5, 0.75, 1, 1.5, 2.5, 4, 6, 10, 16, 25, 35, 50, 70, 95, 120,
    150, 185, 240, 300, 400, 500, 630, 800, 1000,
])}
ORDEN_METODO = {m: i for i, (m, _, _) in enumerate(COLUMNAS)}


def leer_origen() -> list[dict[str, str]]:
    with open(ORIGEN, encoding="utf-8-sig", newline="") as f:
        muestra = f.read(2048)
        f.seek(0)
        delimitador = ";" if muestra.count(";") > muestra.count(",") else ","
        return list(csv.DictReader(f, delimiter=delimitador))


def filas_largas(origen: list[dict[str, str]]) -> dict[tuple[str, str], list[tuple]]:
    salida: dict[tuple[str, str], list[tuple]] = {k: [] for k in SALIDAS}
    for fila in origen:
        material = fila["material"].strip()
        aislacion = "PVC" if "PVC" in fila["isolacao"] else "XLPE"
        clave = (material, aislacion)
        if clave not in SALIDAS:
            continue
        seccion = float(fila["secao_mm2"])
        for metodo, n, col in COLUMNAS:
            crudo = (fila.get(col) or "").strip()
            if not crudo:
                continue
            salida[clave].append((
                seccion, metodo, n, float(crudo),
                int(fila["tabela_NBR"]), material, aislacion,
            ))
    return salida


def escribir(clave: tuple[str, str], filas: list[tuple]) -> Path:
    filas.sort(key=lambda r: (r[4], ORDEN_SECCION[r[0]], ORDEN_METODO[r[1]], r[2]))
    destino = DATA / SALIDAS[clave]
    with open(destino, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow([
            "seccion_mm2", "metodo", "n_conductores", "corriente_a",
            "tabla_nbr", "material", "aislacion",
        ])
        for r in filas:
            w.writerow([f"{r[0]:g}", r[1], r[2], f"{r[3]:g}", r[4], r[5], r[6]])
    return destino


def main() -> None:
    origen = leer_origen()
    for clave, filas in filas_largas(origen).items():
        destino = escribir(clave, filas)
        print(f"{destino.name}: {len(filas)} filas")


if __name__ == "__main__":
    main()
