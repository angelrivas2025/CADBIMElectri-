"""Informe PDF completo: resumen, cuadro de cargas, unifilar, materiales y avisos.

Requiere la dependencia opcional ``fpdf2`` (extra ``export``). El diagrama se
dibuja con las mismas primitivas que el SVG, escaladas a la caja de la página.
"""
from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Any

from core.calc.load_schedule import load_schedule
from exporters.diagram import Circulo, Diagrama, Linea, Rectangulo, Texto, construir_unifilar

MARGEN = 12.0
ANCHO_UTIL = 297.0 - 2 * MARGEN
AZUL = (31, 58, 95)
GRIS_CLARO = (243, 244, 246)
GRIS_LINEA = (214, 219, 226)
TEXTO = (17, 24, 39)
GRIS_TEXTO = (90, 100, 115)
VERDE = (22, 101, 52)
ROJO = (176, 32, 32)


def _texto_pdf(texto: Any) -> str:
    """Adapta el texto a las fuentes base (Latin-1) del PDF."""
    reemplazos = {
        "≥": ">=",
        "≤": "<=",
        "→": "->",
        "—": "-",
        "–": "-",
        "“": '"',
        "”": '"',
        "…": "...",
        "Δ": "d",
        "Ω": "ohm",
        "√": "raiz",
    }
    limpio = "".join(reemplazos.get(c, c) for c in str(texto))
    return limpio.encode("latin-1", "replace").decode("latin-1")


def _num(valor: float | None, decimales: int = 2) -> str:
    if valor is None:
        return "-"
    if decimales == 0:
        return f"{valor:.0f}"
    texto = f"{valor:.{decimales}f}".rstrip("0").rstrip(".")
    return texto or "0"


def _crear_pdf(nombre_proyecto: str):
    try:
        from fpdf import FPDF
    except ImportError as exc:  # pragma: no cover - depende del entorno
        raise RuntimeError(
            "La exportación a PDF requiere fpdf2. Instale el extra: "
            "pip install 'cadbimelectri[export]'"
        ) from exc

    class InformePDF(FPDF):
        def footer(self) -> None:
            self.set_y(-11)
            self.set_font("helvetica", "", 7)
            self.set_text_color(*GRIS_TEXTO)
            self.cell(
                0,
                5,
                _texto_pdf(
                    f"CADBIMElectri · {nombre_proyecto} · Página {self.page_no()}"
                ),
                align="C",
            )

    pdf = InformePDF(orientation="L", unit="mm", format="A4")
    pdf.set_margins(MARGEN, MARGEN, MARGEN)
    pdf.set_auto_page_break(True, margin=16)
    pdf.set_title(_texto_pdf(f"Informe eléctrico — {nombre_proyecto}"))
    pdf.set_author("CADBIMElectri")
    pdf.set_creator("CADBIMElectri")
    return pdf


def _recortar(pdf: Any, texto: str, ancho: float, tamano: float, negrita: bool = False) -> str:
    pdf.set_font("helvetica", "B" if negrita else "", tamano)
    if pdf.get_string_width(texto) <= ancho:
        return texto
    recorte = texto
    while recorte and pdf.get_string_width(recorte + "...") > ancho:
        recorte = recorte[:-1]
    return recorte.rstrip() + "..."


def _fila(
    pdf: Any,
    valores: list[Any],
    anchos: list[float],
    *,
    alto: float = 6.5,
    cabecera: bool = False,
    alineaciones: list[str] | None = None,
    relleno: bool = False,
    tamano: float = 8.0,
) -> None:
    alineaciones = alineaciones or ["L"] * len(anchos)
    if cabecera:
        pdf.set_fill_color(*AZUL)
        pdf.set_text_color(255, 255, 255)
        pdf.set_font("helvetica", "B", tamano)
    else:
        pdf.set_fill_color(*(GRIS_CLARO if relleno else (255, 255, 255)))
        pdf.set_text_color(*TEXTO)
        pdf.set_font("helvetica", "", tamano)

    x0, y0 = pdf.get_x(), pdf.get_y()
    for valor, ancho, alineacion in zip(valores, anchos, alineaciones):
        texto = _recortar(pdf, _texto_pdf(valor), ancho - 2, tamano, cabecera)
        pdf.cell(ancho, alto, texto, align=alineacion, fill=True)
    pdf.set_draw_color(*GRIS_LINEA)
    pdf.set_line_width(0.15)
    pdf.line(x0, y0 + alto, x0 + sum(anchos), y0 + alto)
    pdf.ln(alto)


def _titulo(pdf: Any, texto: str, subtitulo: str | None = None) -> None:
    pdf.set_font("helvetica", "B", 15)
    pdf.set_text_color(*AZUL)
    pdf.cell(0, 9, _texto_pdf(texto), new_x="LMARGIN", new_y="NEXT")
    if subtitulo:
        pdf.set_font("helvetica", "", 8.5)
        pdf.set_text_color(*GRIS_TEXTO)
        pdf.cell(0, 5, _texto_pdf(subtitulo), new_x="LMARGIN", new_y="NEXT")
    pdf.ln(3)


def _parrafo(pdf: Any, texto: str, alto: float = 4.5) -> None:
    pdf.set_x(MARGEN)
    pdf.multi_cell(0, alto, _texto_pdf(texto))


def _portada(pdf: Any, project: dict[str, Any], informe: dict[str, Any]) -> None:
    pdf.add_page()
    pdf.set_font("helvetica", "B", 22)
    pdf.set_text_color(*AZUL)
    pdf.cell(0, 12, "CADBIMElectri", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("helvetica", "B", 15)
    pdf.set_text_color(*TEXTO)
    pdf.cell(0, 9, _texto_pdf(project["project"]["name"]), new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("helvetica", "", 9.5)
    pdf.set_text_color(*GRIS_TEXTO)
    pdf.cell(
        0,
        6,
        _texto_pdf(
            f"Informe eléctrico residencial · NBR 5410 · "
            f"{date.today().isoformat()}"
        ),
        new_x="LMARGIN",
        new_y="NEXT",
    )
    pdf.ln(5)

    prevision = informe.get("prevision") or {}
    demanda = informe.get("demanda") or {}
    circuitos = len((informe.get("dimensionamiento") or {}).get("circuits") or [])
    tarjetas = [
        ("Carga instalada", f"{_num(prevision.get('total_va'), 0)} VA", "previsión 9.5.2"),
        ("Demanda estimada", f"{_num(demanda.get('demanda_va'), 0)} VA", "factores sugeridos"),
        ("Circuitos", str(circuitos), "dimensionados"),
    ]
    ancho = (ANCHO_UTIL - 2 * 6) / 3
    y = pdf.get_y()
    for i, (titulo, valor, nota) in enumerate(tarjetas):
        x = MARGEN + i * (ancho + 6)
        pdf.set_fill_color(*GRIS_CLARO)
        pdf.set_draw_color(*GRIS_LINEA)
        pdf.rect(x, y, ancho, 24, style="DF")
        pdf.set_xy(x + 4, y + 3)
        pdf.set_font("helvetica", "", 8)
        pdf.set_text_color(*GRIS_TEXTO)
        pdf.cell(ancho - 8, 4, _texto_pdf(titulo), new_x="LMARGIN", new_y="NEXT")
        pdf.set_x(x + 4)
        pdf.set_font("helvetica", "B", 15)
        pdf.set_text_color(*AZUL)
        pdf.cell(ancho - 8, 8, _texto_pdf(valor), new_x="LMARGIN", new_y="NEXT")
        pdf.set_x(x + 4)
        pdf.set_font("helvetica", "", 7)
        pdf.set_text_color(*GRIS_TEXTO)
        pdf.cell(ancho - 8, 4, _texto_pdf(nota), new_x="LMARGIN", new_y="NEXT")
    pdf.set_y(y + 30)

    protecciones = informe.get("protecciones") or {}
    dr = protecciones.get("dr_por_circuito") or {}
    clases_dps = protecciones.get("dps_clases") or []
    datos = [
        ("Norma", project["project"]["norm"]),
        ("Sistema", project["project"]["system"]),
        ("Tensión fase-neutro", f"{_num(project['project']['voltage'])} V"),
        ("Ubicación", project["project"].get("location") or "-"),
        ("Circuitos con DR 30 mA", ", ".join(sorted(dr)) or "ninguno"),
        ("DPS", " + ".join(f"clase {c}" for c in clases_dps) or "no requerido"),
        ("Alimentador", _resumen_alimentador(informe.get("alimentador"))),
        ("Salidas", "unifilar.svg · modelo.ifc · cuadro_cargas.csv"),
    ]
    for etiqueta, valor in datos:
        pdf.set_font("helvetica", "B", 8.5)
        pdf.set_text_color(*TEXTO)
        pdf.cell(52, 6.5, _texto_pdf(etiqueta))
        pdf.set_font("helvetica", "", 8.5)
        pdf.cell(0, 6.5, _texto_pdf(valor), new_x="LMARGIN", new_y="NEXT")

    pdf.ln(4)
    errores = informe.get("errores") or []
    if errores:
        pdf.set_text_color(*ROJO)
        pdf.set_font("helvetica", "B", 10)
        pdf.cell(0, 6, f"Estado: {len(errores)} error(es) de cumplimiento", new_x="LMARGIN", new_y="NEXT")
    else:
        pdf.set_text_color(*VERDE)
        pdf.set_font("helvetica", "B", 10)
        pdf.cell(0, 6, "Estado: sin errores de cumplimiento detectados", new_x="LMARGIN", new_y="NEXT")

    pdf.ln(2)
    pdf.set_text_color(*GRIS_TEXTO)
    pdf.set_font("helvetica", "", 7.5)
    _parrafo(
        pdf,
        "Esta herramienta asiste el diseño y no reemplaza al responsable técnico "
        "habilitado. Todo proyecto debe ser revisado por un profesional antes de "
        "su ejecución. Las tablas normativas se reproducen como datos verificados; "
        "no se distribuye texto protegido de la norma.",
    )


def _resumen_alimentador(alimentador: dict[str, Any] | None) -> str:
    if not alimentador:
        return "sin longitud declarada"
    return (
        f"{alimentador.get('phases', 1) + 1}x{_num(alimentador['section_mm2'])} mm² "
        f"{alimentador['material']}/{alimentador['insulation']} · "
        f"In {alimentador['breaker_a']} A · {_num(alimentador['length_m'])} m"
    )


def _cuadro_cargas(pdf: Any, project: dict[str, Any], informe: dict[str, Any]) -> None:
    pdf.add_page()
    _titulo(
        pdf,
        "Cuadro de cargas",
        "Potencia instalada, corriente de proyecto, sección y protección por circuito.",
    )
    anchos = [12, 90, 10, 10, 17, 13, 13, 30, 12, 12, 16, 12]
    alineaciones = ["L", "L", "C", "R", "R", "R", "R", "C", "R", "C", "R", "C"]
    _fila(
        pdf,
        ["ID", "Circuito", "Fase", "Pts", "VA", "A", "L (m)", "Sección", "In (A)", "Curva", "Caída", "DR"],
        anchos,
        cabecera=True,
        alineaciones=alineaciones,
    )

    dr_por_circuito = (informe.get("protecciones") or {}).get("dr_por_circuito") or {}
    circuitos = (informe.get("dimensionamiento") or {}).get("circuits") or []
    total_va = 0.0
    for indice, c in enumerate(circuitos):
        total_va += c.get("power_va") or 0
        _fila(
            pdf,
            [
                c["id"],
                c["name"],
                c.get("phase") or "-",
                c.get("points", 0),
                _num(c.get("power_va"), 0),
                _num(c.get("current_a")),
                _num(c.get("length_m")),
                f"{c['phases'] + 1}x{_num(c['section_mm2'])} mm²",
                c.get("breaker_a") or "-",
                c.get("breaker_curve") or "-",
                f"{_num(c.get('voltage_drop_pct'))} %",
                "Si" if c["id"] in dr_por_circuito else "-",
            ],
            anchos,
            alineaciones=alineaciones,
            relleno=bool(indice % 2),
        )
    _fila(
        pdf,
        ["", "Total", "", "", _num(total_va, 0), "", "", "", "", "", "", ""],
        anchos,
        alineaciones=alineaciones,
    )
    pdf.ln(3)
    pdf.set_font("helvetica", "", 7.5)
    pdf.set_text_color(*GRIS_TEXTO)
    _parrafo(
        pdf,
        "Corriente de proyecto según el número de fases del circuito. El límite "
        "de caída en circuitos terminales es 4 % (NBR 5410 6.2.7). La sección final "
        "es la mayor entre ampacidad, caída y sección mínima normativa.",
    )


def _unifilar(pdf: Any, project: dict[str, Any], informe: dict[str, Any]) -> None:
    pdf.add_page()
    _titulo(pdf, "Diagrama unifilar", "Esquema del tablero, protecciones y circuitos.")
    diagrama = construir_unifilar(project, informe)
    disponible_alto = 210.0 - pdf.get_y() - 18.0
    k = min(ANCHO_UTIL / diagrama.ancho_mm, disponible_alto / diagrama.alto_mm)
    x0 = MARGEN + (ANCHO_UTIL - diagrama.ancho_mm * k) / 2
    y0 = pdf.get_y()

    pdf.set_draw_color(*TEXTO)
    for elemento in diagrama.elementos:
        if isinstance(elemento, Linea):
            pdf.set_line_width(max(0.05, elemento.grosor * k))
            pdf.line(
                x0 + elemento.x1 * k,
                y0 + elemento.y1 * k,
                x0 + elemento.x2 * k,
                y0 + elemento.y2 * k,
            )
        elif isinstance(elemento, Rectangulo):
            pdf.set_line_width(max(0.05, elemento.grosor * k))
            pdf.set_fill_color(*GRIS_CLARO)
            pdf.rect(
                x0 + elemento.x * k,
                y0 + elemento.y * k,
                elemento.ancho * k,
                elemento.alto * k,
                style="DF" if elemento.relleno else "D",
            )
        elif isinstance(elemento, Circulo):
            pdf.set_line_width(max(0.05, elemento.grosor * k))
            pdf.ellipse(
                x0 + (elemento.cx - elemento.r) * k,
                y0 + (elemento.cy - elemento.r) * k,
                2 * elemento.r * k,
                2 * elemento.r * k,
                style="D",
            )
        elif isinstance(elemento, Texto):
            pdf.set_font(
                "helvetica",
                "B" if elemento.negrita else "",
                max(1.0, elemento.tamano * k),
            )
            pdf.set_text_color(*TEXTO)
            texto = _texto_pdf(elemento.contenido)
            ancho = pdf.get_string_width(texto)
            x = x0 + elemento.x * k
            if elemento.ancla == "middle":
                x -= ancho / 2
            elif elemento.ancla == "end":
                x -= ancho
            pdf.text(x, y0 + elemento.y * k, texto)


def _materiales(pdf: Any, informe: dict[str, Any]) -> None:
    pdf.add_page()
    _titulo(pdf, "Lista de materiales", "Cuantificación de lo declarado en el proyecto.")
    anchos = [190, 40, 25]
    _fila(pdf, ["Descripción", "Cantidad", "Unidad"], anchos, cabecera=True,
          alineaciones=["L", "R", "C"])
    items = (informe.get("materiales") or {}).get("items") or []
    for indice, item in enumerate(items):
        _fila(
            pdf,
            [item["descripcion"], _num(item["cantidad"]), item["unidad"]],
            anchos,
            alineaciones=["L", "R", "C"],
            relleno=bool(indice % 2),
        )
    pdf.ln(3)
    pdf.set_font("helvetica", "", 7.5)
    pdf.set_text_color(*GRIS_TEXTO)
    _parrafo(
        pdf,
        "No se agrega desperdicio de obra. Los circuitos sin longitud declarada "
        "no entran en la lista de cables.",
    )


def _prevision_y_avisos(pdf: Any, informe: dict[str, Any]) -> None:
    pdf.add_page()
    _titulo(pdf, "Previsión por ambiente y observaciones")
    anchos = [78, 40, 25, 32, 30, 38]
    _fila(
        pdf,
        ["Ambiente", "Tipo", "Área (m²)", "Iluminación (VA)", "TUG (VA)", "Total (VA)"],
        anchos,
        cabecera=True,
        alineaciones=["L", "L", "R", "R", "R", "R"],
    )
    ambientes = (informe.get("prevision") or {}).get("rooms") or []
    for indice, ambiente in enumerate(ambientes):
        _fila(
            pdf,
            [
                ambiente["name"],
                ambiente["type"],
                _num(ambiente["area_m2"]),
                _num(ambiente["lighting_va"], 0),
                _num(ambiente["tug_va"], 0),
                _num(ambiente["total_va"], 0),
            ],
            anchos,
            alineaciones=["L", "L", "R", "R", "R", "R"],
            relleno=bool(indice % 2),
        )
    pdf.ln(4)

    errores = informe.get("errores") or []
    if errores:
        pdf.set_font("helvetica", "B", 10)
        pdf.set_text_color(*ROJO)
        pdf.cell(0, 6, "Errores de cumplimiento", new_x="LMARGIN", new_y="NEXT")
        pdf.set_font("helvetica", "", 8)
        for error in errores:
            _parrafo(pdf, f"- {error}")
        pdf.ln(2)

    avisos = informe.get("avisos") or []
    pdf.set_font("helvetica", "B", 10)
    pdf.set_text_color(*TEXTO)
    pdf.cell(0, 6, f"Observaciones ({len(avisos)})", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("helvetica", "", 8)
    pdf.set_text_color(*GRIS_TEXTO)
    for aviso in avisos:
        _parrafo(pdf, f"- {aviso}")


def informe_pdf(
    project: dict[str, Any], informe: dict[str, Any], ruta: str | Path
) -> Path:
    """Genera el informe PDF completo y devuelve la ruta escrita."""
    pdf = _crear_pdf(project["project"]["name"])
    _portada(pdf, project, informe)
    _cuadro_cargas(pdf, project, informe)
    _unifilar(pdf, project, informe)
    _materiales(pdf, informe)
    _prevision_y_avisos(pdf, informe)
    destino = Path(ruta)
    destino.parent.mkdir(parents=True, exist_ok=True)
    pdf.output(str(destino))
    return destino
