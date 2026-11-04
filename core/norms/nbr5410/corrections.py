"""Factores de corrección de las tablas 40 a 44 de la NBR 5410.

Los CSV se generan con data/build_factors.py desde el consolidado verificado
(ver data/SOURCE.md). Ninguna función interpola: cuando el valor pedido cae entre
dos filas se usa siempre la fila más desfavorable, y si queda fuera de la tabla se
lanza un error en lugar de extrapolar.
"""
from __future__ import annotations

import csv
from functools import lru_cache
from pathlib import Path

DATA_DIR = Path(__file__).with_name("data")

ARCHIVOS = {
    "temperatura": DATA_DIR / "factores_temperatura.csv",
    "resistividad": DATA_DIR / "factores_resistividad.csv",
    "agrupamiento": DATA_DIR / "factores_agrupamiento.csv",
    "multicamada": DATA_DIR / "factores_multicamada.csv",
    "enterrado": DATA_DIR / "factores_enterrado.csv",
}

DISPOSICIONES = (
    "feixe_1camada",
    "camada_parede_piso",
    "camada_teto",
    "bandeja_perfurada",
    "camada_leito",
)
MODOS_RESISTIVIDAD = ("duto", "enterrado")
AISLACIONES = ("PVC", "XLPE")


class FactorIndefinido(Exception):
    """La tabla no cubre el valor pedido y no se debe extrapolar."""


@lru_cache(maxsize=None)
def _filas(nombre: str) -> tuple[dict[str, str], ...]:
    with open(ARCHIVOS[nombre], encoding="utf-8", newline="") as f:
        return tuple(csv.DictReader(f))


def _mas_pequeno_que_cubre(valor: float, disponibles: list[float], que: str) -> float:
    """Primer valor tabulado >= valor (más desfavorable). Clava al mínimo si es menor."""
    cubren = [v for v in disponibles if v >= valor]
    if cubren:
        return min(cubren)
    raise FactorIndefinido(
        f"{que}: {valor:g} está fuera de la tabla (máximo {max(disponibles):g})"
    )


def factor_temperatura(temperatura_c: float, aislacion: str = "PVC", ambiente: str = "aire") -> float:
    """Tabla 40. El aire se refiere a 30 °C y el suelo a 20 °C."""
    aislacion = aislacion.strip().upper()
    ambiente = ambiente.strip().lower()
    filas = [
        r for r in _filas("temperatura")
        if r["aislacion"] == aislacion and r["ambiente"] == ambiente
    ]
    if not filas:
        raise ValueError(f"Tabla 40 no tiene factores para {aislacion} en {ambiente}")
    valores = {float(r["temperatura_c"]): float(r["factor"]) for r in filas}
    if temperatura_c < min(valores):
        return valores[min(valores)]
    return valores[_mas_pequeno_que_cubre(temperatura_c, sorted(valores), "Temperatura")]


def factor_resistividad(resistividad_km_w: float, modo: str = "enterrado") -> float:
    """Tabla 41. `modo` es 'duto' (en ducto enterrado) o 'enterrado' (directo)."""
    modo = modo.strip().lower()
    if modo not in MODOS_RESISTIVIDAD:
        raise ValueError(f"Modo '{modo}' no válido; use {' o '.join(MODOS_RESISTIVIDAD)}")
    valores = {
        float(r["resistividad_km_w"]): float(r["factor"])
        for r in _filas("resistividad")
        if r["modo"] == modo
    }
    if resistividad_km_w < min(valores):
        return valores[min(valores)]
    return valores[
        _mas_pequeno_que_cubre(resistividad_km_w, sorted(valores), "Resistividad del suelo")
    ]


def factor_agrupamiento(disposicion: str, n_circuitos: int) -> float:
    """Tabla 42. `disposicion` según DISPOSICIONES."""
    disposicion = disposicion.strip().lower()
    if disposicion not in DISPOSICIONES:
        raise ValueError(f"Disposición '{disposicion}' no válida; use {' o '.join(DISPOSICIONES)}")
    if n_circuitos < 1:
        raise ValueError("El número de circuitos agrupados debe ser >= 1")
    for r in _filas("agrupamiento"):
        if (
            r["disposicion"] == disposicion
            and int(r["n_circuitos_min"]) <= n_circuitos <= int(r["n_circuitos_max"])
        ):
            return float(r["factor"])
    maximo = max(int(r["n_circuitos_max"]) for r in _filas("agrupamiento") if r["disposicion"] == disposicion)
    raise FactorIndefinido(
        f"Agrupamiento '{disposicion}': la tabla 42 llega hasta {maximo} circuitos"
    )


def factor_multicamada(n_camadas: int, n_circuitos: int) -> float:
    """Tabla 43, métodos C, E y F."""
    if n_camadas < 2:
        raise ValueError("La tabla 43 aplica a partir de 2 camadas")
    for r in _filas("multicamada"):
        if (
            int(r["n_camadas_min"]) <= n_camadas <= int(r["n_camadas_max"])
            and int(r["n_circuitos_min"]) <= n_circuitos <= int(r["n_circuitos_max"])
        ):
            return float(r["factor"])
    raise FactorIndefinido(
        f"Tabla 43 no cubre {n_camadas} camadas con {n_circuitos} circuitos"
    )


def factor_enterrado(n_circuitos: int, distancia: float | str) -> float:
    """Tabla 44. `distancia` en metros o '1D' (un diámetro) entre circuitos."""
    if n_circuitos < 2:
        raise ValueError("La tabla 44 aplica a partir de 2 circuitos enterrados")
    filas = [r for r in _filas("enterrado") if int(r["n_circuitos"]) == n_circuitos]
    if not filas:
        raise FactorIndefinido(f"Tabla 44 no cubre {n_circuitos} circuitos enterrados")

    if isinstance(distancia, str) and distancia.strip().upper().endswith("D"):
        pedido = float(distancia.strip().upper().removesuffix("D"))
        clave = "distancia_diametros"
    else:
        pedido = float(distancia)
        clave = "distancia_m"

    candidatos = sorted(
        (float(r[clave]), float(r["factor"])) for r in filas if r[clave] != ""
    )
    # Más cerca = peor factor; se toma la distancia tabulada mayor que no supere la pedida.
    aplicables = [(d, f) for d, f in candidatos if d <= pedido + 1e-9]
    if not aplicables:
        raise FactorIndefinido(f"Tabla 44: la distancia mínima tabulada es {candidatos[0][0]:g}")
    return aplicables[-1][1]


def factor_total(*factores: float) -> float:
    """Producto de los factores de corrección aplicables a un circuito."""
    total = 1.0
    for f in factores:
        if f <= 0:
            raise ValueError(f"Factor de corrección no positivo: {f}")
        total *= f
    return total


def validar_factores() -> list[str]:
    """Coherencia de las tablas: los factores deben empeorar al agravarse el parámetro."""
    problemas: list[str] = []

    for aislacion in AISLACIONES:
        for ambiente in ("aire", "solo"):
            valores = sorted(
                (float(r["temperatura_c"]), float(r["factor"]))
                for r in _filas("temperatura")
                if r["aislacion"] == aislacion and r["ambiente"] == ambiente
            )
            for (t1, f1), (t2, f2) in zip(valores, valores[1:]):
                if f2 >= f1:
                    problemas.append(
                        f"Temperatura {aislacion}/{ambiente}: {f2:g} a {t2:g} °C no es menor "
                        f"que {f1:g} a {t1:g} °C"
                    )

    for modo in MODOS_RESISTIVIDAD:
        valores = sorted(
            (float(r["resistividad_km_w"]), float(r["factor"]))
            for r in _filas("resistividad")
            if r["modo"] == modo
        )
        for (r1, f1), (r2, f2) in zip(valores, valores[1:]):
            if f2 >= f1:
                problemas.append(
                    f"Resistividad {modo}: {f2:g} a {r2:g} no es menor que {f1:g} a {r1:g}"
                )

    for disposicion in DISPOSICIONES:
        valores = sorted(
            (int(r["n_circuitos_min"]), float(r["factor"]))
            for r in _filas("agrupamiento")
            if r["disposicion"] == disposicion
        )
        for (n1, f1), (n2, f2) in zip(valores, valores[1:]):
            if f2 > f1:
                problemas.append(
                    f"Agrupamiento {disposicion}: {f2:g} con {n2} circuitos supera "
                    f"a {f1:g} con {n1}"
                )

    grupos: dict[int, dict[int, dict[int, float]]] = {}
    for r in _filas("multicamada"):
        camadas = int(r["n_camadas_min"])
        circuitos = int(r["n_circuitos_min"])
        grupos.setdefault(camadas, {})[circuitos] = float(r["factor"])
    for camadas, por_circuito in sorted(grupos.items()):
        previos = sorted(por_circuito.items())
        for (c1, f1), (c2, f2) in zip(previos, previos[1:]):
            if f2 > f1:
                problemas.append(
                    f"Multicamada {camadas}: {f2:g} con {c2} circuitos supera a {f1:g} con {c1}"
                )
    for (camadas_a, filas_a), (camadas_b, filas_b) in zip(
        sorted(grupos.items()), sorted(grupos.items())[1:]
    ):
        for circuitos, fa in sorted(filas_a.items()):
            fb = filas_b.get(circuitos)
            if fb is not None and fb > fa:
                problemas.append(
                    f"Multicamada con {circuitos} circuitos: {camadas_b} camadas ({fb:g}) "
                    f"supera a {camadas_a} camadas ({fa:g})"
                )

    for n in sorted({int(r["n_circuitos"]) for r in _filas("enterrado")}):
        valores = sorted(
            (float(r["distancia_m"]), float(r["factor"]))
            for r in _filas("enterrado")
            if int(r["n_circuitos"]) == n and r["distancia_m"] != ""
        )
        for (d1, f1), (d2, f2) in zip(valores, valores[1:]):
            if f2 < f1:
                problemas.append(
                    f"Enterrado con {n} circuitos: {f2:g} a {d2:g} m es menor que {f1:g} a {d1:g} m"
                )

    por_distancia: dict[float, list[tuple[int, float]]] = {}
    for r in _filas("enterrado"):
        if r["distancia_m"] != "":
            por_distancia.setdefault(float(r["distancia_m"]), []).append(
                (int(r["n_circuitos"]), float(r["factor"]))
            )
    for distancia, valores in sorted(por_distancia.items()):
        for (n1, f1), (n2, f2) in zip(sorted(valores), sorted(valores)[1:]):
            if f2 > f1:
                problemas.append(
                    f"Enterrado a {distancia:g} m: {f2:g} con {n2} circuitos supera "
                    f"a {f1:g} con {n1}"
                )

    return problemas
