"""Caída de tensión de circuitos de 1, 2 y 3 fases.

Modelo resistivo (reactancia despreciada, cos φ = 1), conservador para la parte
resistiva. La resistencia se calcula con la física del cobre; es una aproximación
*ideal* (conductor macizo), por eso se aplica un margen provisional hasta cargar las
resistencias reales de los conductores (IEC 60228).

Factores de caída:
- 1 o 2 fases: los dos conductores llevan la corriente → 2 · I · L · R
- 3 fases equilibradas: √3 · I · L · R

El límite porcentual no tiene valor por defecto: lo fija la norma (ver limits.py).
"""
from __future__ import annotations

from math import sqrt

from core.norms.nbr5410.ampacity import SECCIONES_COMERCIALES

RHO_COBRE_20C = 0.017241   # Ω·mm²/m, cobre recocido estándar (IACS)
ALFA_COBRE = 0.00393       # 1/°C, coeficiente de temperatura del cobre
MARGEN_PROVISIONAL = 1.10  # compensa que los cables reales no son macizos ideales


def resistencia_ohm_por_m(seccion_mm2: float, temperatura_c: float = 70.0, material: str = "Cu") -> float:
    if seccion_mm2 <= 0:
        raise ValueError("La sección debe ser positiva")
    if material.capitalize() == "Al":
        rho = 0.028264 * (1 + 0.00403 * (temperatura_c - 20.0))
    elif material.capitalize() == "Cu":
        rho = RHO_COBRE_20C * (1 + ALFA_COBRE * (temperatura_c - 20.0))
    else:
        raise ValueError(f"Material no soportado: {material}")
    return rho / seccion_mm2


def _factor_caida(n_fases: int) -> float:
    if n_fases in (1, 2):
        return 2.0
    if n_fases == 3:
        return sqrt(3)
    raise ValueError(f"n_fases debe ser 1, 2 o 3 (recibido: {n_fases})")


def caida_tension_v(
    corriente_a: float,
    longitud_m: float,
    seccion_mm2: float,
    temperatura_c: float = 70.0,
    margen: float = MARGEN_PROVISIONAL,
    n_fases: int = 1,
    material: str = "Cu",
) -> float:
    """Caída de tensión en voltios. `longitud_m` es la longitud de ida del tramo."""
    r = resistencia_ohm_por_m(seccion_mm2, temperatura_c, material)
    return _factor_caida(n_fases) * corriente_a * longitud_m * r * margen


def caida_tension_pct(
    corriente_a: float,
    longitud_m: float,
    seccion_mm2: float,
    tension_fase_v: float,
    n_fases: int = 1,
    **kw,
) -> float:
    """Caída en % de la tensión de servicio (fase-neutro o de línea según n_fases)."""
    tension_servicio = tension_fase_v if n_fases == 1 else tension_fase_v * sqrt(3)
    caida = caida_tension_v(corriente_a, longitud_m, seccion_mm2, n_fases=n_fases, **kw)
    return caida / tension_servicio * 100


def seccion_minima_por_caida(
    corriente_a: float,
    longitud_m: float,
    tension_fase_v: float,
    limite_pct: float,
    n_fases: int = 1,
    **kw,
) -> float:
    """Menor sección comercial que cumple el límite de caída (límite_pct lo da la norma)."""
    for seccion in SECCIONES_COMERCIALES:
        if caida_tension_pct(
            corriente_a, longitud_m, seccion, tension_fase_v, n_fases=n_fases, **kw
        ) <= limite_pct:
            return seccion
    raise ValueError("Ninguna sección comercial cumple el límite de caída de tensión")
