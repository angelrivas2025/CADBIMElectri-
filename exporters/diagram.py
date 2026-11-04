"""Modelo geométrico del diagrama unifilar, independiente del formato de salida.

Un único constructor produce las primitivas (líneas, rectángulos, círculos y
textos) y tanto el exportador SVG como el PDF las dibujan. Así ambos formatos
muestran exactamente la misma geometría.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from core.calc.currents import corriente_de_circuito
from core.calc.load_schedule import FASES_POR_SISTEMA, load_schedule
from core.calc.validate import validar_proyecto

ANCHO_MM = 297.0
ALTO_MIN_MM = 160.0
X_BUS = 30.0
Y_BUS = 46.0
ALTO_FILA = 15.0
X_TEXTO = 62.0


@dataclass(frozen=True)
class Linea:
    x1: float
    y1: float
    x2: float
    y2: float
    grosor: float = 0.3


@dataclass(frozen=True)
class Rectangulo:
    x: float
    y: float
    ancho: float
    alto: float
    grosor: float = 0.3
    relleno: bool = False


@dataclass(frozen=True)
class Circulo:
    cx: float
    cy: float
    r: float
    grosor: float = 0.3


@dataclass(frozen=True)
class Texto:
    x: float
    y: float
    contenido: str
    tamano: float = 7.0
    ancla: str = "start"
    negrita: bool = False


Elemento = Linea | Rectangulo | Circulo | Texto


@dataclass(frozen=True)
class Diagrama:
    ancho_mm: float
    alto_mm: float
    elementos: tuple[Elemento, ...]


def _num(valor: float | None, decimales: int = 2) -> str:
    if valor is None:
        return "?"
    if decimales == 0:
        return f"{valor:.0f}"
    texto = f"{valor:.{decimales}f}".rstrip("0").rstrip(".")
    return texto or "0"


def construir_unifilar(
    project: dict[str, Any], informe: dict[str, Any] | None = None
) -> Diagrama:
    """Construye el unifilar a partir del proyecto y su informe de validación."""
    if informe is None:
        informe = validar_proyecto(project)

    elementos: list[Elemento] = []
    sistema = project["project"]["system"]
    fases = FASES_POR_SISTEMA[sistema]
    tension = project["project"]["voltage"]
    nombre = project["project"]["name"]

    elementos.append(Texto(12, 16, f"Diagrama unifilar — {nombre}", 14, negrita=True))
    elementos.append(
        Texto(
            12,
            22,
            f"NBR 5410 · sistema {sistema} · {_num(tension)} V fase-neutro · "
            f"{len(project['circuits'])} circuitos",
            8.5,
        )
    )

    demanda = informe.get("demanda") or {}
    demanda_va = demanda.get("demanda_va")
    corriente_demanda = None
    if demanda_va:
        corriente_demanda = corriente_de_circuito(demanda_va, len(fases), tension)

    alimentador = informe.get("alimentador")
    if alimentador:
        linea_alimentador = (
            f"Alimentador {len(fases) + 1}x{_num(alimentador['section_mm2'])} mm² "
            f"{alimentador['material']}/{alimentador['insulation']} · "
            f"In {alimentador['breaker_a']} A · L {_num(alimentador['length_m'])} m"
        )
    else:
        linea_alimentador = "Alimentador sin longitud declarada"
    elementos.append(Texto(X_BUS + 8, 30, linea_alimentador, 7.5))
    if demanda_va:
        elementos.append(
            Texto(
                X_BUS + 8,
                37,
                f"Demanda {_num(demanda_va, 0)} VA · {_num(corriente_demanda, 1)} A",
                7.5,
            )
        )

    # Acometida y disyuntor general.
    elementos.append(Texto(X_BUS + 3, 25, "Origen", 6.5))
    elementos.append(Linea(X_BUS, 25, X_BUS, Y_BUS))
    elementos.append(Linea(X_BUS - 2.5, 25, X_BUS + 2.5, 25))
    elementos.append(Rectangulo(X_BUS - 5, 30.5, 10, 5, relleno=True))
    elementos.append(Linea(X_BUS - 3.5, 34, X_BUS + 3.5, 32))

    protecciones = informe.get("protecciones") or {}
    clases_dps = protecciones.get("dps_clases") or []
    if clases_dps:
        y_dps = Y_BUS - 5
        elementos.append(Linea(X_BUS, y_dps, 38, y_dps))
        elementos.append(Rectangulo(38, y_dps - 3, 10, 6, relleno=True))
        elementos.append(Texto(43, y_dps + 1.2, "DPS", 6, ancla="middle"))
        elementos.append(Texto(50, y_dps + 1, f"clase {' + '.join(clases_dps)}", 6.5))

    dimensionado = (informe.get("dimensionamiento") or {}).get("circuits") or []
    por_id = {c["id"]: c for c in dimensionado}
    dr_por_circuito = protecciones.get("dr_por_circuito") or {}

    y = Y_BUS + 8
    for circuito in project["circuits"]:
        dim = por_id.get(circuito["id"])
        fase = circuito.get("phase") or "?"
        elementos.append(Linea(X_BUS, y, 31, y))
        elementos.append(Rectangulo(31, y - 2.5, 10, 5, relleno=True))
        elementos.append(Linea(33, y + 1, 39, y - 1))
        tiene_dr = circuito["id"] in dr_por_circuito
        if tiene_dr:
            elementos.append(Linea(41, y, 45, y))
            elementos.append(Circulo(47.5, y, 2.5))
            elementos.append(Texto(47.5, y + 1.2, "DR", 5, ancla="middle"))
            elementos.append(Linea(50, y, X_TEXTO - 4, y))
        else:
            elementos.append(Linea(41, y, X_TEXTO - 4, y))

        cabecera = f"{circuito['id']} · {circuito['name']} [{fase}]"
        elementos.append(Texto(X_TEXTO, y - 1.2, cabecera, 8, negrita=True))
        if dim:
            conductores = dim["phases"] + 1
            detalle = (
                f"{conductores}x{_num(dim['section_mm2'])} mm² "
                f"{dim['material']}/{dim['insulation']} · "
                f"In {dim['breaker_a']} A curva {dim['breaker_curve']}"
            )
            carga = (
                f"{_num(dim['power_va'], 0)} VA · {_num(dim['current_a'])} A · "
                f"caída {_num(dim['voltage_drop_pct'])} %"
            )
        else:
            detalle = "Sin dimensionar: revisar datos del circuito"
            carga = f"{_num(circuito.get('power_va'), 0)} VA"
        if tiene_dr:
            carga += " · DR 30 mA"
        elementos.append(Texto(X_TEXTO, y + 3, detalle, 7))
        elementos.append(Texto(X_TEXTO, y + 6.8, carga, 7))
        y += ALTO_FILA

    alto_bus = y - ALTO_FILA + 5
    elementos.append(Linea(X_BUS, Y_BUS, X_BUS, alto_bus, grosor=0.5))

    cuadro = load_schedule(project)
    y_resumen = max(alto_bus + 14, 150.0)
    resumen = " · ".join(
        f"Fase {fase}: {_num(valor, 0)} VA" for fase, valor in cuadro["by_phase_va"].items()
    )
    if cuadro["imbalance_pct"] is not None:
        resumen += f" · desbalance {_num(cuadro['imbalance_pct'], 1)} %"
    elementos.append(Texto(12, y_resumen, resumen, 8))
    elementos.append(
        Texto(
            12,
            y_resumen + 6,
            "Secciones y protecciones calculadas según NBR 5410. "
            "Verificar en obra y con el responsable técnico habilitado.",
            6.5,
        )
    )

    alto = max(ALTO_MIN_MM, y_resumen + 12)
    return Diagrama(ANCHO_MM, alto, tuple(elementos))
