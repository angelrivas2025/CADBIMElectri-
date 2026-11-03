"""Caída de tensión en circuitos monofásicos de dos conductores (fase-neutro).

v0.1 - modelo resistivo (reactancia despreciada, cos φ = 1, valor conservador para
la parte resistiva). La resistencia se calcula con la física del cobre; es una
aproximación *ideal* (conductor macizo), por eso se aplica un margen provisional
hasta cargar las resistencias reales de la norma de conductores (IEC 60228).
El límite porcentual NO tiene valor por defecto: lo fija la norma aplicable.
"""
from __future__ import annotations

from core.norms.nbr5410.ampacity import SECCIONES_COMERCIALES

RHO_COBRE_20C = 0.017241   # Ω·mm²/m, cobre recocido estándar (IACS)
ALFA_COBRE = 0.00393       # 1/°C, coeficiente de temperatura del cobre
MARGEN_PROVISIONAL = 1.10  # compensa que los cables reales no son macizos ideales


def resistencia_ohm_por_m(seccion_mm2: float, temperatura_c: float = 70.0) -> float:
    rho = RHO_COBRE_20C * (1 + ALFA_COBRE * (temperatura_c - 20.0))
    return rho / seccion_mm2


def caida_tension_v(
    corriente_a: float,
    longitud_m: float,
    seccion_mm2: float,
    temperatura_c: float = 70.0,
    margen: float = MARGEN_PROVISIONAL,
) -> float:
    """Caída total (ida y vuelta) en voltios."""
    return 2 * corriente_a * longitud_m * resistencia_ohm_por_m(seccion_mm2, temperatura_c) * margen


def caida_tension_pct(
    corriente_a: float, longitud_m: float, seccion_mm2: float, tension_v: float, **kw
) -> float:
    return caida_tension_v(corriente_a, longitud_m, seccion_mm2, **kw) / tension_v * 100


def seccion_minima_por_caida(
    corriente_a: float,
    longitud_m: float,
    tension_v: float,
    limite_pct: float,
    **kw,
) -> float:
    """Menor sección comercial que cumple el límite de caída (límite_pct lo da la norma)."""
    for seccion in SECCIONES_COMERCIALES:
        if caida_tension_pct(corriente_a, longitud_m, seccion, tension_v, **kw) <= limite_pct:
            return seccion
    raise ValueError("Ninguna sección comercial cumple el límite de caída de tensión")
