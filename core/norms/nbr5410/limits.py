"""Límites de caída de tensión de la NBR 5410:2004, 6.2.7.

Tabla de límites según el origen de la instalación:

- A: desde los bornes secundarios de transformador MT/BT propio ......... 7 %
- B: desde los bornes del transformador de la distribuidora ............. 7 %
- C: desde el punto de entrega, suministro en tensión secundaria ........ 5 %
- D: desde los bornes de salida de un generador propio .................. 7 %

Notas de la norma:
1. En ningún caso la caída en los circuitos terminales puede superar 4 %.
2. En los casos A, B y D, si las líneas principales superan 100 m, el límite sube
   0,005 % por metro excedente, hasta un máximo de 0,5 % adicional.
"""
from __future__ import annotations

LIMITE_TERMINAL_PCT = 4.0
LIMITE_TOTAL_PCT = 7.0
LIMITE_ALIMENTADOR_PCT = 5.0  # caso C: total desde el punto de entrega

LIMITE_POR_CASO_PCT = {"A": 7.0, "B": 7.0, "C": 5.0, "D": 7.0}
CASOS_CON_EXTENSION = frozenset({"A", "B", "D"})

LONGITUD_BASE_M = 100.0
AMPLIACION_PCT_POR_M = 0.005
AMPLIACION_MAXIMA_PCT = 0.5

TOLERANCIA_PCT = 1e-9


class CasoEntregaInvalido(ValueError):
    """El caso de origen de la instalación no es A, B, C ni D."""


def limite_caso_pct(caso: str, longitud_m: float = 0.0) -> float:
    """Límite total (%). La ampliación por longitud solo aplica a los casos A, B y D."""
    caso = caso.strip().upper()
    if caso not in LIMITE_POR_CASO_PCT:
        raise CasoEntregaInvalido(f"Caso '{caso}' no válido; use A, B, C o D")
    limite = LIMITE_POR_CASO_PCT[caso]
    if caso in CASOS_CON_EXTENSION and longitud_m > LONGITUD_BASE_M:
        extra = AMPLIACION_PCT_POR_M * (longitud_m - LONGITUD_BASE_M)
        limite += min(extra, AMPLIACION_MAXIMA_PCT)
    return limite


def validar_caida(
    *,
    terminal_pct: float | None = None,
    total_pct: float | None = None,
    caso: str = "C",
    longitud_m: float = 0.0,
) -> list[str]:
    """Problemas de caída de tensión, o lista vacía.

    `terminal_pct` es la caída de un circuito terminal y `total_pct` la suma desde el
    punto de entrega (alimentador + terminales).
    """
    problemas: list[str] = []
    if terminal_pct is not None and terminal_pct > LIMITE_TERMINAL_PCT + TOLERANCIA_PCT:
        problemas.append(
            f"Caída del circuito terminal {terminal_pct:.2f} % supera el máximo de "
            f"{LIMITE_TERMINAL_PCT:.1f} %"
        )
    if total_pct is not None:
        limite = limite_caso_pct(caso, longitud_m)
        if total_pct > limite + TOLERANCIA_PCT:
            problemas.append(
                f"Caída total {total_pct:.2f} % supera el límite de {limite:.3f} % "
                f"(caso {caso.strip().upper()}, {longitud_m:.0f} m)"
            )
    return problemas
