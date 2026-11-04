"""Render del diagrama unifilar a SVG (formato abierto, sin dependencias)."""
from __future__ import annotations

from html import escape
from pathlib import Path

from exporters.diagram import Circulo, Diagrama, Linea, Rectangulo, Texto

PT_A_MM = 25.4 / 72.0


def _n(valor: float) -> str:
    texto = f"{valor:.2f}".rstrip("0").rstrip(".")
    return texto or "0"


def unifilar_svg(diagrama: Diagrama) -> str:
    partes = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        (
            f'<svg xmlns="http://www.w3.org/2000/svg" '
            f'width="{_n(diagrama.ancho_mm)}mm" height="{_n(diagrama.alto_mm)}mm" '
            f'viewBox="0 0 {_n(diagrama.ancho_mm)} {_n(diagrama.alto_mm)}">'
        ),
        "<title>Diagrama unifilar</title>",
        '<rect width="100%" height="100%" fill="#ffffff"/>',
        '<g stroke="#1f2937" fill="none" stroke-linecap="round" stroke-linejoin="round">',
    ]

    for elemento in diagrama.elementos:
        if isinstance(elemento, Linea):
            partes.append(
                f'<line x1="{_n(elemento.x1)}" y1="{_n(elemento.y1)}" '
                f'x2="{_n(elemento.x2)}" y2="{_n(elemento.y2)}" '
                f'stroke-width="{_n(elemento.grosor)}"/>'
            )
        elif isinstance(elemento, Rectangulo):
            relleno = "#f3f4f6" if elemento.relleno else "none"
            partes.append(
                f'<rect x="{_n(elemento.x)}" y="{_n(elemento.y)}" '
                f'width="{_n(elemento.ancho)}" height="{_n(elemento.alto)}" '
                f'fill="{relleno}" stroke-width="{_n(elemento.grosor)}"/>'
            )
        elif isinstance(elemento, Circulo):
            partes.append(
                f'<circle cx="{_n(elemento.cx)}" cy="{_n(elemento.cy)}" '
                f'r="{_n(elemento.r)}" stroke-width="{_n(elemento.grosor)}"/>'
            )
        elif isinstance(elemento, Texto):
            ancla = {"start": "start", "middle": "middle", "end": "end"}[elemento.ancla]
            peso = "bold" if elemento.negrita else "normal"
            partes.append(
                f'<text x="{_n(elemento.x)}" y="{_n(elemento.y)}" '
                f'font-family="Helvetica, Arial, sans-serif" '
                f'font-size="{_n(elemento.tamano * PT_A_MM)}" '
                f'text-anchor="{ancla}" font-weight="{peso}" fill="#111827" stroke="none">'
                f"{escape(elemento.contenido)}</text>"
            )

    partes.append("</g>")
    partes.append("</svg>")
    return "\n".join(partes) + "\n"


def escribir_svg(diagrama: Diagrama, ruta: str | Path) -> Path:
    destino = Path(ruta)
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_text(unifilar_svg(diagrama), encoding="utf-8")
    return destino
