"""Genera los CSV de factores de corrección (tablas 40 a 44) desde el consolidado.

Uso:
    python core/norms/nbr5410/data/build_factors.py

Origen: data/source/fatores_40_44_origem.csv, extraído de las tablas 40 a 44 de la
NBR 5410:2004 reproducidas por la guía de Prysmian. Ver SOURCE.md.
"""
from __future__ import annotations

import csv
import re
from pathlib import Path

DATA = Path(__file__).resolve().parent
ORIGEN = DATA / "source" / "fatores_40_44_origem.csv"

DISPOSICIONES = {
    "agrup_feixe_1camada": "feixe_1camada",
    "agrup_camada_parede_piso": "camada_parede_piso",
    "agrup_camada_teto": "camada_teto",
    "agrup_bandeja_perfurada": "bandeja_perfurada",
    "agrup_camada_leito": "camada_leito",
}

# Columna del origen -> etiqueta de aislación (tabla 40).
AISLACIONES = {"PVC_70C": "PVC", "XLPE_EPR_90C": "XLPE"}

# Tabla 41: las dos columnas son modos de instalación, no aislaciones.
MODOS_RESISTIVIDAD = {"PVC_70C": "duto", "XLPE_EPR_90C": "enterrado"}

MAX_N = 999


def leer_origen() -> list[dict[str, str]]:
    with open(ORIGEN, encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f, delimiter=";"))


def rango(texto: str) -> tuple[int, int]:
    """'2' -> (2,2); '4-5' -> (4,5); '>=9' -> (9,999)."""
    texto = texto.strip()
    if texto.startswith(">="):
        return int(texto[2:]), MAX_N
    if "-" in texto:
        a, b = texto.split("-")
        return int(a), int(b)
    if texto.startswith("circuitos_"):
        return rango(texto.removeprefix("circuitos_"))
    return int(texto), int(texto)


def valores(texto: str) -> list[float]:
    return [float(v) for v in re.split(r"\s*/\s*", texto.strip()) if v]


def escribir(nombre: str, encabezado: list[str], filas: list[list]) -> Path:
    destino = DATA / nombre
    with open(destino, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(encabezado)
        w.writerows(filas)
    print(f"{nombre}: {len(filas)} filas")
    return destino


def temperatura(origen) -> list[list]:
    filas = []
    for r in origen:
        if r["tabela_NBR"] != "40":
            continue
        ambiente = "aire" if r["grupo"] == "temperatura_ar_C" else "solo"
        for columna, aislacion in AISLACIONES.items():
            crudo = (r[columna] or "").strip()
            if crudo:
                filas.append([ambiente, float(r["parametro"]), aislacion, float(crudo), 40])
    filas.sort(key=lambda f: (f[0], f[2], f[1]))
    return filas


def resistividad(origen) -> list[list]:
    filas = []
    for r in origen:
        if r["tabela_NBR"] != "41":
            continue
        for columna, modo in MODOS_RESISTIVIDAD.items():
            filas.append([modo, float(r["parametro"]), float(r[columna]), 41])
    filas.sort(key=lambda f: (f[0], f[1]))
    return filas


def agrupamiento(origen) -> list[list]:
    filas = []
    for r in origen:
        if r["tabela_NBR"] != "42":
            continue
        disposicion = DISPOSICIONES[r["grupo"]]
        minimo, maximo = rango(r["parametro"])
        filas.append([disposicion, minimo, maximo, float(r["PVC_70C"]), 42])
    filas.sort(key=lambda f: (f[0], f[1]))
    return filas


def multicamada(origen) -> list[list]:
    filas = []
    for r in origen:
        if r["tabela_NBR"] != "43":
            continue
        camadas = rango(r["grupo"].removeprefix("multicamada_camadas_"))
        grupos = r["parametro"].removeprefix("circuitos_").split("/")
        for grupo, factor in zip(grupos, valores(r["PVC_70C"])):
            minimo, maximo = rango(grupo)
            filas.append([camadas[0], camadas[1], minimo, maximo, factor, 43])
    filas.sort(key=lambda f: (f[0], f[2]))
    return filas


def enterrado(origen) -> list[list]:
    filas = []
    for r in origen:
        if r["tabela_NBR"] != "44":
            continue
        n = rango(r["grupo"].removeprefix("enterrado_circuitos_"))[0]
        distancias = r["parametro"].removeprefix("dist_").split("/")
        for distancia, factor in zip(distancias, valores(r["PVC_70C"])):
            distancia = distancia.removesuffix("m").strip()
            if distancia.upper().endswith("D"):
                metros, diametros = "", float(distancia.upper().removesuffix("D"))
            else:
                metros, diametros = float(distancia), ""
            filas.append([n, metros, diametros, factor, 44])
    filas.sort(key=lambda f: (f[0], f[1] if f[1] != "" else f[2]))
    return filas


def main() -> None:
    origen = leer_origen()
    escribir(
        "factores_temperatura.csv",
        ["ambiente", "temperatura_c", "aislacion", "factor", "tabla_nbr"],
        temperatura(origen),
    )
    escribir(
        "factores_resistividad.csv",
        ["modo", "resistividad_km_w", "factor", "tabla_nbr"],
        resistividad(origen),
    )
    escribir(
        "factores_agrupamiento.csv",
        ["disposicion", "n_circuitos_min", "n_circuitos_max", "factor", "tabla_nbr"],
        agrupamiento(origen),
    )
    escribir(
        "factores_multicamada.csv",
        ["n_camadas_min", "n_camadas_max", "n_circuitos_min", "n_circuitos_max", "factor", "tabla_nbr"],
        multicamada(origen),
    )
    escribir(
        "factores_enterrado.csv",
        ["n_circuitos", "distancia_m", "distancia_diametros", "factor", "tabla_nbr"],
        enterrado(origen),
    )


if __name__ == "__main__":
    main()
